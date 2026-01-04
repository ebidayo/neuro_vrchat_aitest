"""Minimal state machine for Phase1
States: IDLE -> ALERT -> SEARCH -> IDLE
Triggers: 'alert', 'search_done', 'reset', 'search_timeout'
Provides listener callback support to notify on state changes.
"""
import asyncio
import enum
import logging
import time
import datetime
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class State(enum.IntEnum):
    # Numeric mapping compatible with README v1.2
    IDLE = 0
    GREET = 1
    TALK = 2
    REACT = 3
    FOCUS = 4
    ALERT = 5
    SEARCH = 6
    ERROR = 7
    RECOVER = 8


class StateMachine:
    """Enhanced state machine for Phase1:

    - Maintains scalar internal state: valence/arousal/confidence/glitch/curiosity/social_pressure
    - Runs an internal tick loop to update scalars and enforce timeouts
    - ALERT is preemptive: previous state is saved and restored after ALERT ends
    """
    def __init__(
        self,
        alert_to_search_delay: float = 3.0,
        search_timeout: float = 30.0,
        talk_silence_timeout: float = 30.0,
        error_recover_time: float = 5.0,
    ):
        self.state: State = State.IDLE
        self._prev_state: State = State.IDLE
        self.alert_to_search_delay = alert_to_search_delay
        self.search_timeout = search_timeout
        self.talk_silence_timeout = talk_silence_timeout
        self.error_recover_time = error_recover_time

        # internal scalar parameters
        self.valence: float = 0.0        # -1..1
        self.arousal: float = 0.1       # 0..1
        self.confidence: float = 0.9    # 0..1
        self.glitch: float = 0.0        # 0..1
        self.curiosity: float = 0.05    # 0..1
        self.social_pressure: float = 0.0

        self._listeners: List[Callable[[State], None]] = []
        self._loop_task: Optional[asyncio.Task] = None
        self._state_task: Optional[asyncio.Task] = None
        self._silence_timer: Optional[float] = None
        self._last_speaking_ts: Optional[float] = None
        self._state_enter_ts: float = time.time()
        # pending interrupt if an ALERT or other high priority event should be deferred until speech end
        self._pending_interrupt: tuple | None = None
        # current alert payload (v1.2 normalized)
        self.current_alert: dict | None = None
        self._last_alert_was_update: bool = False

        # search-related tracking
        self.pending_net_query: str | None = None
        self.pending_net_sources: list | None = None
        self.current_search_result: dict | None = None
        self._last_search_ts: float = 0.0

        # Idle presence and starter support
        self._last_idle_action_ts: float = 0.0
        self.idle_action_interval_range: tuple = (12.0, 25.0)
        self.pending_idle_presence: dict | None = None

        self.pending_starter: dict | None = None
        self._last_starter_ts: float = 0.0
        self.starter_cooldown: float = 60.0
        # small silence required since last speech before starter may fire
        self.starter_min_silence_sec: float = 2.0

        # speaker focus tracking
        self.active_speaker_id: str | None = None
        self.speaker_threshold: float = 0.75

        # name-learning / alias flow
        # active_speaker_alias stores the last seen alias such as 'unknown_1' or 'alice'
        self.active_speaker_alias: str | None = None
        # when an unknown speaker is detected, pending_name_request holds the interaction state:
        # {'alias':'unknown_1', 'asked_at': ts, 'stage': 'ask'|'asked'|'confirm'|'retry', 'name_candidate': None}
        self.pending_name_request: dict | None = None
        # when user confirms, pending_name_set is filled and main is expected to persist via SpeakerStore
        self.pending_name_set: dict | None = None
        # after persistence main may set pending_saved_name so SM can trigger an ack plan
        self.pending_name_saved: dict | None = None
        # cooldown between name requests
        self.name_request_cooldown_sec: float = 120.0
        self._last_name_request_ts: float = 0.0

        # speaker streak detection: require multiple consistent unknown hits before prompting
        self._speaker_streak_alias: str | None = None
        self._speaker_streak_count: int = 0
        self.name_ask_min_streak: int = 2
        self.name_ask_min_conf: float = 0.65
        self.name_ask_min_interval_sec: float = 180.0
        # last asked timestamps per alias to enforce min interval
        self._last_name_asked_at: dict = {}

        # GREET support for known speakers
        self.pending_greet: dict | None = None
        self._last_greet_ts_by_speaker: dict = {}
        self.greet_cooldown_sec: float = 180.0
        self.greet_min_silence_sec: float = 1.2
        self.greet_min_conf: float = 0.65
        self.greet_requires_known_name: bool = True

        logger.debug("StateMachine initialized: %s", self.__dict__)

    def should_prompt_name(self, alias: str, conf: float, now: float | None = None, has_profile: bool = False, state: State | None = None) -> bool:
        """Decide whether we should prompt the user for a name for the given alias.

        Conditions:
        - alias is an "unknown" style alias (prefix 'unknown')
        - confidence >= name_ask_min_conf
        - streak_count >= name_ask_min_streak
        - not already having a persisted profile (has_profile==False)
        - not in ALERT/SEARCH
        - respects global cooldown and per-alias min interval
        """
        now = now or time.time()
        if not alias or not str(alias).startswith("unknown"):
            return False
        if conf < self.name_ask_min_conf:
            return False
        # streak must be sufficient
        if self._speaker_streak_alias != alias or self._speaker_streak_count < self.name_ask_min_streak:
            return False
        if has_profile:
            return False
        s = state or self.state
        if s in (State.ALERT, State.SEARCH):
            return False
        # global cooldown
        if now - getattr(self, "_last_name_request_ts", 0.0) < getattr(self, "name_request_cooldown_sec", 120.0):
            return False
        # per-alias min interval
        last_alias_asked = self._last_name_asked_at.get(alias, 0.0)
        if now - last_alias_asked < getattr(self, "name_ask_min_interval_sec", 180.0):
            return False
        return True

    def should_schedule_greet(self, alias: str, conf: float, now: float | None = None, has_profile: bool = False, state: State | None = None, now_dt: Optional[datetime.datetime] = None) -> bool:
        """Return True if conditions are met to schedule a greet for a known speaker.

        Conditions:
        - has_profile must be True (unless greet_requires_known_name False)
        - conf >= greet_min_conf
        - not in ALERT/SEARCH
        - not in the middle of a name-asking flow (pending_name_request)
        - speaker-specific cooldown respected
        - optional silence requirement: if recent speaking (self._last_speaking_ts) is too recent, allow scheduling but do not interrupt mid-chunk (we will queue)

        ``now_dt`` is an optional datetime to use for deterministic testing and greet_type decision.
        """
        import datetime as _dt
        now = now or time.time()
        if not alias:
            return False
        if self.greet_requires_known_name and not has_profile:
            return False
        if conf < self.greet_min_conf:
            return False
        s = state or self.state
        if s in (State.ALERT, State.SEARCH):
            return False
        if self.pending_name_request:
            return False
        # per-speaker cooldown
        speaker_key = alias
        last = self._last_greet_ts_by_speaker.get(speaker_key, 0.0)
        if now - last < getattr(self, "greet_cooldown_sec", 180.0):
            return False
        # optional silence requirement: prefer not to greet if someone is speaking very recently
        if getattr(self, "_last_speaking_ts", None) and (now - self._last_speaking_ts) < getattr(self, "greet_min_silence_sec", 1.2):
            # still allow scheduling but not immediate (we'll queue via _maybe_interrupt)
            # we'll not block scheduling here; if you want to strictly avoid scheduling, return False
            pass
        return True

    def add_listener(self, callback: Callable[[State], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        logger.info("State changed -> %s", self.state)
        for cb in self._listeners:
            try:
                cb(self.state)
            except Exception:
                logger.exception("Listener failed")

    def start(self) -> None:
        """Start internal loop (must be called from running event loop)."""
        if not self._loop_task:
            self._loop_task = asyncio.create_task(self._run_loop())

    def stop(self) -> None:
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()

    async def _run_loop(self) -> None:
        """Periodic update: scalar dynamics, timeouts, and automatic transitions."""
        try:
            while True:
                self._tick(1.0)
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.debug("StateMachine loop cancelled")

    def _tick(self, dt: float) -> None:
        """Update scalar state over dt seconds."""
        # curiosity grows slowly in IDLE when not speaking
        if self.state == State.IDLE and (not self._last_speaking_ts or (time.time() - self._last_speaking_ts) > 5.0):
            self.curiosity = min(1.0, self.curiosity + 0.01 * dt)
        else:
            # decay curiosity slowly
            self.curiosity = max(0.0, self.curiosity - 0.005 * dt)

        # glitch decays
        self.glitch = max(0.0, self.glitch - 0.02 * dt)
        # confidence slowly recovers toward 1, but can be reduced by failures
        self.confidence = min(1.0, self.confidence + 0.005 * dt)
        # arousal decays slightly to baseline
        self.arousal = max(0.05, self.arousal - 0.01 * dt)

        # automatic SEARCH trigger by curiosity threshold
        if self.state == State.IDLE and self.curiosity > 0.6:
            logger.info("Curiosity threshold reached -> starting SEARCH")
            self.start_search()

        # Idle presence actions (low-frequency, unobtrusive)
        now = time.time()
        if self.state == State.IDLE and (not self._last_speaking_ts or (now - self._last_speaking_ts) > 1.0) and not self.current_alert and not self.pending_net_query:
            # schedule idle presence at random intervals
            interval = self.idle_action_interval_range[0] + ( (self.idle_action_interval_range[1] - self.idle_action_interval_range[0]) * ( (now % 10) / 10.0 ) )
            if now - self._last_idle_action_ts >= interval:
                # pick one simple action: think / aside / pause / self_correct (one chunk only)
                import random
                r = random.random()
                if r < 0.35:
                    kind = "think"
                    text = "…"
                elif r < 0.7:
                    kind = "aside"
                    text = "んー。"
                elif r < 0.85:
                    kind = "pause"
                    text = ""
                else:
                    kind = "self_correct"
                    text = "あ、いや。"
                # create a pending idle presence payload and notify listeners
                self.pending_idle_presence = {"type": kind, "text": text, "ts": now}
                self._last_idle_action_ts = now
                logger.info("Scheduled idle presence action: %s %s", kind, text)
                # notify listeners (state unchanged) so external handlers may choose to emit
                self._notify()

        # Starter attempt: only in IDLE, not in SEARCH/ALERT, and not speaking recently
        if self.state == State.IDLE and not self.current_alert and not self.pending_net_query:
            now = time.time()
            if self.social_pressure >= 0.4 and self.confidence >= 0.35 and (now - self._last_starter_ts) >= self.starter_cooldown and (not self._last_speaking_ts or (now - self._last_speaking_ts) >= self.starter_min_silence_sec):
                # Fire a starter: immediate short transition to TALK as per spec
                # pick a short starter phrase
                import random
                starters = ["ねえ。", "今、大丈夫？", "ちょっと聞いていい？"]
                text = random.choice(starters)
                self._last_starter_ts = now
                self.pending_starter = {"text": text, "ts": now}
                logger.info("Starter fired: %s", text)
                # transition to TALK to deliver starter
                self._enter_state(State.TALK)

        # TALK->IDLE on silence
        if self.state == State.TALK and self._last_speaking_ts:
            if time.time() - self._last_speaking_ts > self.talk_silence_timeout:
                logger.info("Talk silence timeout -> back to IDLE")
                self._enter_state(State.IDLE)

    def notify_speaking(self) -> None:
        """Call this when talking starts / continues."""
        self._last_speaking_ts = time.time()
        # being active reduces curiosity
        self.curiosity = max(0.0, self.curiosity - 0.05)

    def on_event(self, event: str, payload: dict | None = None, **kwargs) -> None:
        """Generic event interface for external triggers.

        Extended to support v1.2 event names (tick, vad_start/vad_end, stt_partial/stt_final,
        net_query, curiosity_spike, alert_new/alert_update/alert_clear, tts_chunk_done, fails, recover_done, etc.)
        """
        logger.debug("Event received: %s payload=%s current=%s", event, payload, self.state)

        # simple mapping of alias events
        if event == "alert" or event == "alert_new":
            # handle new alert with priority interruption semantics
            p = payload or {}
            # normalize and store in state machine for main to consume
            self.current_alert = p
            self._last_alert_was_update = False
            severity = int(p.get("severity", 0))
            allow_mid = p.get("allow_mid", False)
            # immediate interrupt or schedule based on payload 'allow_mid'
            self._maybe_interrupt(State.ALERT, reason=p, allow_mid_chunk=allow_mid)
            # increase scalar responses
            self.glitch = min(1.0, self.glitch + 0.3)
            self.arousal = min(1.0, self.arousal + 0.3)
            # schedule auto end
            loop = asyncio.get_event_loop()
            if self._state_task and not self._state_task.done():
                self._state_task.cancel()
            self._state_task = loop.create_task(self._auto_end_alert())
            return

        if event == "alert_update":
            # update existing alert in-place if it matches
            p = payload or {}
            if self.current_alert and p.get("alert_event_id") == self.current_alert.get("alert_event_id"):
                prev_seq = int(self.current_alert.get("update_seq", 1))
                seq = int(p.get("update_seq", prev_seq))
                if seq > prev_seq:
                    self.current_alert.update(p)
                    self._last_alert_was_update = True
                    # small scalar nudges for updates
                    self.glitch = min(1.0, self.glitch + 0.05 * int(p.get("severity", 0)))
                else:
                    # stale update ignored
                    logger.debug("Stale alert update ignored: %s (known=%s)", seq, prev_seq)
            else:
                # no matching alert; treat as new
                self.on_event("alert_new", p)
            return

        if event == "alert_clear":
            # clear alert and return to previous
            # keep current_alert for potential clear-speech handling if needed
            if self.state == State.ALERT:
                self._enter_state(self._prev_state)
            # mark cleared
            if self.current_alert:
                self.current_alert["cleared"] = True
            return

        if event == "start_search" or event == "net_query":
            # network-driven searches allowed; payload may contain query
            p = payload or {}
            query = p.get("query")
            sources = p.get("sources", [])
            if query:
                self.pending_net_query = query
                self.pending_net_sources = sources
            # rate-limit / cooldown check
            now = time.time()
            cooldown = getattr(self, "search_cooldown", 60.0)
            if now - getattr(self, "_last_search_ts", 0.0) < cooldown:
                logger.info("Search suppressed due to cooldown: %s", query)
                return
            # do not start SEARCH if in ALERT
            if self.state == State.ALERT:
                logger.info("Search suppressed due to ALERT state: %s", query)
                return
            # allow queued interrupt (do not mid-chunk interrupt)
            self._maybe_interrupt(State.SEARCH, reason={"query": query, "sources": sources}, allow_mid_chunk=False)
            return

        if event == "curiosity_spike":
            # only start search if allowed by cooldown
            now = time.time()
            cooldown = getattr(self, "search_cooldown", 1800.0)
            last = getattr(self, "_last_search_ts", 0.0)
            if now - last >= cooldown:
                self._last_search_ts = now
                self.start_search()
            return

        if event == "talk_start" or event == "vad_start":
            self._enter_state(State.TALK)
            self.notify_speaking()
            return

        if event == "talk_end" or event == "vad_end":
            self.mark_speech_done()
            self._enter_state(State.IDLE)
            return

        if event == "stt_partial":
            # payload: {text:...}; can be logged
            return

        if event == "stt_final":
            # payload: {text:..., speaker_id:..., speaker_confidence:..., speaker_alias:...}
            p = payload or {}
            # If speaker info is present, possibly adjust focus/attitude
            sid = p.get("speaker_id")
            sconf = float(p.get("speaker_confidence", 0.0)) if p.get("speaker_confidence") is not None else 0.0
            if sid and sconf >= getattr(self, "speaker_threshold", 0.75):
                logger.info("Recognized active speaker %s (conf=%.2f)", sid, sconf)
                self.active_speaker_id = sid
                # nudges to reflect increased attention
                self.social_pressure = min(1.0, self.social_pressure + 0.2)
                self.confidence = min(1.0, self.confidence + 0.1)
            else:
                # unknown or low confidence
                self.active_speaker_id = None

            # optionally record alias (e.g., 'unknown_1'); main may pass this if available
            alias = p.get("speaker_alias")
            if alias:
                self.active_speaker_alias = alias
                # update streak counters for stability gating
                try:
                    conf = float(p.get("speaker_confidence", 0.0)) if p.get("speaker_confidence") is not None else 0.0
                except Exception:
                    conf = 0.0
                # if alias is same as previous and meets confidence threshold, increment
                if alias == self._speaker_streak_alias:
                    if conf >= self.name_ask_min_conf:
                        self._speaker_streak_count += 1
                    else:
                        # low confidence for this alias does not increase streak
                        self._speaker_streak_count = max(0, self._speaker_streak_count - 1)
                else:
                    # new alias, start streak only if conf sufficient
                    self._speaker_streak_alias = alias
                    self._speaker_streak_count = 1 if conf >= self.name_ask_min_conf else 0

                logger.debug("Speaker streak updated: alias=%s count=%s conf=%.2f", self._speaker_streak_alias, self._speaker_streak_count, conf)
                # If this alias appears stable and prompting conditions are met, create pending name request
                if self.should_prompt_name(alias, conf, now=time.time(), has_profile=False, state=self.state):
                    # avoid duplicate pending requests
                    if not self.pending_name_request:
                        self.pending_name_request = {"alias": alias, "asked_at": time.time(), "stage": "ask", "name_candidate": None, "confidence": conf}
                        self._last_name_request_ts = time.time()
                        self._last_name_asked_at[alias] = time.time()
                        logger.info("Auto-created pending name request for %s due to stable streak", alias)
                        self._maybe_interrupt(State.TALK, reason={"name_request": True}, allow_mid_chunk=False)
                        self._notify()

                # GREET decision: if speaker is known (has_profile indicated in payload), not in name flow, and gate passes
                has_profile = bool(p.get("has_profile", False))
                speaker_key = p.get("speaker_key") or alias
                # allow test code to pass a datetime via payload for deterministic greet_type selection
                now_dt = p.get("now_dt")
                if has_profile and not self.pending_name_request and self.should_schedule_greet(alias, conf, now=time.time(), has_profile=has_profile, state=self.state, now_dt=now_dt):
                    # prepare greet; use name if present in payload (main can pass display_name) else main should look up later
                    name = p.get("display_name") or None
                    # decide greet_type using now_dt if provided, else use current local time
                    try:
                        if now_dt:
                            from core.utils.time_utils import decide_greet_type_from_dt
                            gt = decide_greet_type_from_dt(now_dt)
                        else:
                            from datetime import datetime
                            from core.utils.time_utils import decide_greet_type_from_dt
                            gt = decide_greet_type_from_dt(datetime.now())
                    except Exception:
                        gt = None
                    self.pending_greet = {"alias": alias, "speaker_key": speaker_key, "name": name, "greet_type": gt, "ts": time.time()}
                    self._last_greet_ts_by_speaker[speaker_key] = time.time()
                    logger.info("Pending greet scheduled for %s (key=%s) greet_type=%s", alias, speaker_key, gt)
                    self._maybe_interrupt(State.GREET, reason={"greet": True}, allow_mid_chunk=False)
                    self._notify()

            # also reduce curiosity slightly on hearing final transcription
            if p.get("text"):
                self.curiosity = max(0.0, self.curiosity - 0.05)
            return

        if event == "speaker_unknown_detected":
            # payload: {'alias':..., 'confidence':...}
            p = payload or {}
            alias = p.get("alias")
            conf = float(p.get("confidence", 0.0)) if p.get("confidence") is not None else 0.0
            now = time.time()
            # Do not ask if we're in ALERT/SEARCH, if too recent, or if a pending request exists
            if self.state in (State.ALERT, State.SEARCH):
                logger.info("Deferring name ask due to high-priority state: %s", self.state.name)
                return
            if self.pending_name_request:
                logger.info("Name request already pending for %s, skipping", self.pending_name_request.get("alias"))
                return
            # use helper gate to decide whether to prompt
            if not alias:
                return
            if not self.should_prompt_name(alias, conf, now=now, has_profile=False, state=self.state):
                logger.info("Should not prompt name for %s yet (gate not passed)", alias)
                return
            # create pending request and queue a weak interrupt to TALK (ask at next chunk boundary)
            self.pending_name_request = {"alias": alias, "asked_at": now, "stage": "ask", "name_candidate": None, "confidence": conf}
            self._last_name_request_ts = now
            self._last_name_asked_at[alias] = now
            logger.info("Pending name request created for alias %s", alias)
            # queue a weak interrupt (do not interrupt mid-chunk)
            self._maybe_interrupt(State.TALK, reason={"name_request": True}, allow_mid_chunk=False)
            # notify listeners so main can emit the ask plan at boundary
            self._notify()
            return

        if event == "name_answer":
            # payload: {'alias':..., 'name':..., 'confidence':...}
            p = payload or {}
            alias = p.get("alias")
            name = p.get("name")
            if not self.pending_name_request or self.pending_name_request.get("alias") != alias:
                logger.info("Ignoring name_answer for %s: no pending request", alias)
                return
            # store candidate and move to confirmation stage
            self.pending_name_request["name_candidate"] = name
            self.pending_name_request["stage"] = "confirm"
            self.pending_name_request["candidate_confidence"] = float(p.get("confidence", 0.9))
            logger.info("Name candidate received for %s: %s -> asking for confirmation", alias, name)
            # notify listeners so main can emit confirmation plan
            self._notify()
            return

        if event == "name_confirm_yes":
            # payload can optionally include alias and name; prefer pending candidate
            p = payload or {}
            if not self.pending_name_request:
                logger.info("No pending name request to confirm")
                return
            alias = p.get("alias") or self.pending_name_request.get("alias")
            name = p.get("name") or self.pending_name_request.get("name_candidate")
            if not alias or not name:
                logger.info("Confirm received but missing alias/name: %s %s", alias, name)
                return
            # Set pending_name_set so main can persist it via SpeakerStore
            self.pending_name_set = {"alias": alias, "name": name, "consent": True, "ts": time.time()}
            # clear the pending request flow
            self.pending_name_request = None
            logger.info("Name confirmed for %s -> pending set to save: %s", alias, name)
            # notify listeners so main can persist and emit saved plan
            self._notify()
            return

        if event == "name_confirm_no":
            # user corrected; move back to ask/retry
            if not self.pending_name_request:
                logger.info("No pending name request to reject")
                return
            self.pending_name_request["stage"] = "retry"
            self.pending_name_request["name_candidate"] = None
            logger.info("Name confirmation rejected; will retry ask for alias %s", self.pending_name_request.get("alias"))
            self._notify()
            return

        if event == "forget_name":
            # payload: {'name_or_alias': ...}
            p = payload or {}
            self.pending_forget = {"name_or_alias": p.get("name_or_alias"), "ts": time.time()}
            # notify main to perform deletion and emit ack
            self._notify()
            return

        if event == "search_result":
            p = payload or {}
            # store result for main to use when entering TALK
            self.current_search_result = p
            self._last_search_ts = time.time()
            # transition to TALK to deliver results
            self._enter_state(State.TALK)
            return

        if event == "search_failed":
            p = payload or {}
            self.current_search_result = {"ok": False, "error": p.get("error", "unknown")}
            self._last_search_ts = time.time()
            self._enter_state(State.TALK)
            return

        if event == "error" or event.endswith("_fail"):
            self._enter_state(State.ERROR)
            self.confidence = max(0.0, self.confidence - 0.25)
            self.glitch = min(1.0, self.glitch + 0.4)
            loop = asyncio.get_event_loop()
            if self._state_task and not self._state_task.done():
                self._state_task.cancel()
            self._state_task = loop.create_task(self._auto_recover())
            return

        if event == "recover_done":
            self._enter_state(State.IDLE)
            return

        if event == "tick":
            # payload may include dt
            dt = (payload or {}).get("dt", 1.0)
            self._tick(dt)
            return

        # fallback to legacy events
        if event == "search_result":
            success = kwargs.get("success", True)
            self._on_search_result(success)
            return

        if event == "reset":
            self._enter_state(State.IDLE)
            self.confidence = 0.9
            self.glitch = 0.0
            self.curiosity = 0.05
            return

        logger.debug("Unhandled event: %s", event)

    def _enter_state(self, s: State) -> None:
        self.state = s
        self._state_enter_ts = time.time()
        self._notify()

    def start_search(self) -> None:
        logger.info("Entering SEARCH state")
        self._enter_state(State.SEARCH)
        # while searching, increase arousal a bit, and reset curiosity
        self.arousal = min(1.0, self.arousal + 0.15)
        self.curiosity = max(0.0, self.curiosity - 0.3)
        # schedule timeout
        loop = asyncio.get_event_loop()
        if self._state_task and not self._state_task.done():
            self._state_task.cancel()
        self._state_task = loop.create_task(self._search_timeout())

    async def _search_timeout(self) -> None:
        try:
            await asyncio.sleep(self.search_timeout)
            logger.info("Search timeout -> returning to previous state and marking ERROR if needed")
            # on timeout, mark error and return
            self.on_event("error")
            self._enter_state(self._prev_state if self._prev_state != State.SEARCH else State.IDLE)
        except asyncio.CancelledError:
            logger.debug("Search task cancelled")

    def _on_search_result(self, success: bool) -> None:
        if success:
            logger.info("Search succeeded -> returning to previous state")
            self._enter_state(self._prev_state if self._prev_state != State.SEARCH else State.IDLE)
            # increase confidence
            self.confidence = min(1.0, self.confidence + 0.1)
            # reset retry attempts
            setattr(self, "_retry_attempts", 0)
        else:
            logger.info("Search failed -> reducing confidence and increasing glitch")
            self.confidence = max(0.0, self.confidence - 0.2)
            self.glitch = min(1.0, self.glitch + 0.3)
            # schedule retry with backoff
            attempts = getattr(self, "_retry_attempts", 0)
            if attempts < 5:
                backoff = min(60.0, 2 ** attempts)
                logger.info("Scheduling search retry in %s seconds (attempt %s)", backoff, attempts + 1)
                loop = asyncio.get_event_loop()
                if self._state_task and not self._state_task.done():
                    self._state_task.cancel()
                self._state_task = loop.create_task(self._delayed_retry_search(backoff))
                setattr(self, "_retry_attempts", attempts + 1)
            else:
                logger.info("Max retries reached, returning to IDLE")
                self._enter_state(self._prev_state if self._prev_state != State.SEARCH else State.IDLE)
                setattr(self, "_retry_attempts", 0)

    async def _delayed_retry_search(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            logger.debug("Retry delay elapsed, starting search")
            self.start_search()
        except asyncio.CancelledError:
            logger.debug("Delayed retry cancelled")

    async def _auto_recover(self) -> None:
        try:
            await asyncio.sleep(self.error_recover_time)
            # attempt recover
            if self.confidence < 0.2:
                # failed recover -> go IDLE
                self._enter_state(State.IDLE)
            else:
                self._enter_state(State.RECOVER)
                await asyncio.sleep(1.0)
                self._enter_state(State.IDLE)
        except asyncio.CancelledError:
            logger.debug("Recover cancelled")

    async def _auto_end_alert(self) -> None:
        try:
            # Alert is short-lived by default; after some seconds return to prev
            await asyncio.sleep(4.0)
            self._enter_state(self._prev_state)
        except asyncio.CancelledError:
            logger.debug("Alert auto end cancelled")

    def mark_speech_done(self) -> None:
        # called when a speech chunk finishes
        self._last_speaking_ts = time.time()
        # if an interrupt was queued during speech, trigger it now
        if getattr(self, "_pending_interrupt", None):
            new_state, reason = self._pending_interrupt
            logger.info("Applying queued interrupt -> %s", new_state)
            self._pending_interrupt = None
            self._prev_state = self.state
            # if the queued interrupt is a starter, persist the starter payload
            if reason and isinstance(reason, dict) and reason.get("starter"):
                self.pending_starter = reason
            self._enter_state(new_state)

    def _maybe_interrupt(self, new_state: State, reason: dict | None = None, allow_mid_chunk: bool = False) -> None:
        """Decide whether to interrupt immediately or queue until speech ends.

        If we are currently in TALK and allow_mid_chunk is False, queue the interrupt to be
        applied when the current speech finishes.
        """
        if allow_mid_chunk or self.state not in (State.TALK, State.GREET, State.REACT):
            logger.info("Immediate interrupt to %s", new_state)
            self._prev_state = self.state
            self._enter_state(new_state)
        else:
            logger.info("Queuing interrupt %s until next speech boundary", new_state)
            self._pending_interrupt = (new_state, reason)


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.DEBUG)

    async def demo():
        sm = StateMachine()
        def l(s):
            print("state ->", s)
        sm.add_listener(l)
        sm.start()
        print("Trigger alert")
        sm.on_event("alert")
        await asyncio.sleep(6)
        print("Trigger start_search")
        sm.start_search()
        await asyncio.sleep(2)
        sm.on_event("search_result", success=True)
        await asyncio.sleep(2)
    asyncio.run(demo())






