async def test_get_hits_the_in_process_api_app(api_client):
    body = await api_client.get("/countries")
    assert set(body.keys()) == {"featured", "expanded", "sovereign"}


async def test_get_drops_none_valued_params(api_client):
    # scope omitted entirely (None) must not be sent as the literal string "None" -- the
    # API's own scope default ("expanded") should kick in instead.
    body = await api_client.get("/historical/timeseries", params={"gas": "co2", "scope": None})
    assert body["gas"] == "co2"


async def test_get_raises_on_4xx(api_client):
    import httpx

    try:
        await api_client.get("/countries/Nowhereland/profile")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 404
    else:
        raise AssertionError("expected HTTPStatusError for an unknown country")
