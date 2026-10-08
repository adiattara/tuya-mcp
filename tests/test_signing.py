from tuya_mcp.signing import EMPTY_BODY_SHA256, build_url, sign, string_to_sign

# Worked examples from https://developer.tuya.com/en/docs/iot/new-singnature?id=Kbw0q34cs2e5g
CLIENT_ID = "1KAD46OrT9HafiKdsXeg"
SECRET = "4OHBOnWOqaEC1mWXOpVL3yV50s0qGSRC"
T = "1588925778000"
NONCE = "5138cc3a9033d69856923fd07b491173"
SIGNED_HEADERS = [
    ("area_id", "29a33e8796834b1efa6"),
    ("call_id", "8afdb70ab2ed11eb85290242ac130003"),
]


def test_empty_body_hash() -> None:
    assert EMPTY_BODY_SHA256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_token_request_signature_matches_official_vector() -> None:
    sts = string_to_sign("GET", "/v1.0/token?grant_type=1", signed_headers=SIGNED_HEADERS)
    signature = sign(client_id=CLIENT_ID, secret=SECRET, t=T, nonce=NONCE, string_to_sign=sts)
    assert signature == "9E48A3E93B302EEECC803C7241985D0A34EB944F40FB573C7B5C2A82158AF13E"


def test_business_request_signature_matches_official_vector() -> None:
    url = build_url("/v2.0/apps/schema/users", {"page_size": 50, "page_no": 1})
    sts = string_to_sign("GET", url, signed_headers=SIGNED_HEADERS)
    signature = sign(
        client_id=CLIENT_ID,
        secret=SECRET,
        t=T,
        nonce=NONCE,
        access_token="3f4eda2bdec17232f67c0b188af3eec1",
        string_to_sign=sts,
    )
    assert signature == "AE4481C692AA80B25F3A7E12C3A5FD9BBF6251539DD78E565A1A72A508A88784"


def test_build_url_sorts_query_keys() -> None:
    assert build_url("/p", {"size": 20, "last_row_key": "abc"}) == "/p?last_row_key=abc&size=20"
    assert build_url("/p") == "/p"
    assert build_url("/p", {"flag": True}) == "/p?flag=true"


def test_string_to_sign_without_headers() -> None:
    assert string_to_sign("get", "/v1.0/token?grant_type=1") == (
        f"GET\n{EMPTY_BODY_SHA256}\n\n/v1.0/token?grant_type=1"
    )


def test_signature_is_uppercase_hex() -> None:
    signature = sign(client_id="a", secret="b", t="1", string_to_sign="x")
    assert signature == signature.upper()
    assert len(signature) == 64
