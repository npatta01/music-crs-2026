"""batch_chat response-generation options (state-conditioning, XML item, echo-retry).

Builds a CRS_BASELINE via __new__ and injects fakes so we don't load any model/DB."""
from __future__ import annotations

from mcrs.crs_baseline import CRS_BASELINE


class FakeQU:
    def __init__(self, states):
        self._states = states
        self.last_traces = []

    def batch_compile_track_ids(self, session_memories, topk, user_ids=None):
        self.last_traces = [{"state": s} for s in self._states]
        return [["t1"], ["t2"]]


class FinalRecommendationQU:
    def __init__(self):
        self.last_traces = []

    def batch_compile_track_ids(self, session_memories, topk, user_ids=None):
        self.last_traces = [
            {
                "extracted_state": {"turn_intent": "play jazz"},
                "final_recommendation": {
                    "track_ids": ["t2", "t1"],
                    "primary_track_id": "t2",
                    "source_stage": "l3_mock",
                    "ranking_mode": "lgbm",
                },
            }
        ]
        return [["t1", "t2"]]


class FakeItemDB:
    metadata_dict = {
        "t1": {"track_name": ["Olvidarte"], "artist_name": ["Arjona"], "album_name": ["A"],
               "tag_list": ["balada", "spanish"]},
        "t2": {"track_name": ["Rock"], "artist_name": ["Band"], "album_name": ["B"], "tag_list": ["rock"]},
    }

    def id_to_metadata(self, track_id, use_semantic_id=False):
        m = self.metadata_dict[track_id]
        return f"title: {m['track_name'][0]} | artist: {m['artist_name'][0]} | tags: {', '.join(m['tag_list'])}"


class FakeLM:
    """Echoes the context + item so the test can see what was fed."""
    def batch_response_generation(self, sys_prompts, contexts, items):
        return [f"CTX[{contexts[i][0]['content']}]|ITEM[{items[i]}]" for i in range(len(contexts))]


def _make_crs(**resp_opts):
    crs = CRS_BASELINE.__new__(CRS_BASELINE)
    crs.qu = FakeQU(states=[{"turn_intent": "play jazz"}, {"turn_intent": "play rock"}])
    crs.lm = FakeLM()
    crs.item_db = FakeItemDB()
    crs.retrieval_topk = 20
    crs.role_prompt = {"role_play": "", "response_generation": "SYS", "personalization": ""}
    crs.user_db = None
    crs.response_conditioning = resp_opts.get("conditioning", "transcript")
    crs.response_item_format = resp_opts.get("item_format", "plain")
    crs.response_max_tags = resp_opts.get("max_tags", 10)
    crs.response_echo_retries = resp_opts.get("echo_retries", 0)
    crs.response_style = resp_opts.get("style", "")
    return crs


def _batch():
    return [
        {"user_query": "play jazz", "user_id": None, "session_memory": []},
        {"user_query": "play rock", "user_id": None, "session_memory": []},
    ]


def test_state_conditioning_feeds_state_block_not_transcript():
    crs = _make_crs(conditioning="state", item_format="xml")
    out = crs.batch_chat(_batch())
    # response context was the [LISTENER CONTEXT] state block, with the turn_intent
    assert "[LISTENER CONTEXT]" in out[0]["response"]
    assert "play jazz" in out[0]["response"]
    # item was the XML block, not the raw "title: ..." pipe string
    assert "<recommended_track>" in out[0]["response"]
    assert "Olvidarte" in out[0]["response"]


def test_latest_state_conditioning_feeds_goal_language_latest_and_style():
    crs = _make_crs(
        conditioning="latest_state",
        item_format="xml",
        style="Write about only the selected track.",
    )
    out = crs.batch_chat(
        [
            {
                "user_query": "play jazz",
                "user_id": None,
                "session_memory": [{"role": "user", "content": "older request"}],
                "session_meta": {
                    "conversation_goal": {"listener_goal": "discover modal jazz"},
                    "user_profile": {"preferred_language": "English"},
                },
            }
        ]
    )

    response = out[0]["response"]
    assert "Listener goal: discover modal jazz" in response
    assert "Preferred language: English" in response
    assert "Latest user request: play jazz" in response
    assert "Current request: play jazz" in response
    assert "older request" not in response
    assert "Response style: Write about only the selected track." in response


def test_transcript_default_uses_session_memory_and_plain_item():
    crs = _make_crs()  # defaults: transcript + plain
    out = crs.batch_chat(_batch())
    assert "[LISTENER CONTEXT]" not in out[0]["response"]
    assert "title: Olvidarte" in out[0]["response"]  # plain metadata item


def test_echo_retry_regenerates_metadata_echo():
    crs = _make_crs(conditioning="state", item_format="xml", echo_retries=2)

    class EchoThenGoodLM:
        def __init__(self):
            self.calls = 0

        def batch_response_generation(self, sys_prompts, contexts, items):
            return ["title: Olvidarte | artist: Arjona | tags: x", "ok reply"]

        def response_generation(self, sys_p, context, item, max_new_tokens=512):
            self.calls += 1
            return "recovered natural reply"

    crs.lm = EchoThenGoodLM()
    out = crs.batch_chat(_batch())
    assert out[0]["response"] == "recovered natural reply"  # echo regenerated
    assert out[1]["response"] == "ok reply"  # non-echo left alone


def test_response_generation_uses_final_recommendation_primary_track():
    crs = _make_crs(conditioning="state", item_format="plain")
    crs.retrieval_topk = 1
    crs.qu = FinalRecommendationQU()

    out = crs.batch_chat([{"user_query": "play jazz", "user_id": None, "session_memory": []}])

    assert out[0]["retrieval_items"] == ["t2"]
    assert out[0]["retrieval_items"] == out[0]["trace"]["final_recommendation"]["track_ids"][:1]
    assert "title: Rock" in out[0]["response"]
    assert "title: Olvidarte" not in out[0]["response"]


def test_batch_chat_exposes_stage_timings():
    crs = _make_crs(conditioning="state", item_format="plain")

    out = crs.batch_chat(_batch())

    assert out
    assert set(crs.last_batch_timings) >= {
        "prepare_inputs",
        "retrieval",
        "recommend_items",
        "response_context",
        "response_generation",
        "assemble_results",
    }
    assert all(value >= 0.0 for value in crs.last_batch_timings.values())
