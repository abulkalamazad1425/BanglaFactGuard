from app.shared.utils.domains import allowed_domains_for, is_allowed_host


def test_allowed_domains_are_the_source_and_its_registered_channels_without_duplicates():
    config = {"allowed_domains": ["https://www.prothomalo.com/", "en.prothomalo.com", "prothomalo.com", ""]}
    assert allowed_domains_for("prothomalo.com", config) == ["prothomalo.com", "en.prothomalo.com"]
    assert allowed_domains_for(None, None) == []


def test_host_must_be_an_allowed_domain_or_its_subdomain():
    allowed = ["jugantor.com"]
    assert is_allowed_host("https://www.jugantor.com/a/1", allowed)
    assert is_allowed_host("m.jugantor.com", allowed)
    assert not is_allowed_host("jugantor.com.evil.net", allowed)   # deceptive suffix
    assert not is_allowed_host("notjugantor.com", allowed)
    assert not is_allowed_host("", allowed)
