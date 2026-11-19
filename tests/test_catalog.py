"""Tests of the server lists."""
import json
import os

import pytest

from conftest import system
from fakes import ACCOUNT_PASSWORD

from cghostgui import paths
from cghostgui.catalog import Catalog, parse_table
from cghostgui.errors import CgError, LoginRequired


def logged_in() -> Catalog:
    """Create a catalogue with a valid login.

    Returns:
        Catalogue.
    """
    catalog = Catalog()
    catalog.username, catalog.password = "me", ACCOUNT_PASSWORD
    return catalog


def test_parse_table() -> None:
    """The header and rule lines are dropped."""
    assert parse_table("+--+\n| a |\n+--+\n| 1 |\n") == [["1"]]


def test_login_needed() -> None:
    """Without password or token the user is asked."""
    with pytest.raises(LoginRequired):
        Catalog().countries()


def test_wrong_login_is_forgotten() -> None:
    """A rejected password is dropped and leaves no login file."""
    catalog = Catalog()
    catalog.password = "wrong"
    with pytest.raises(LoginRequired, match="abgelehnt"):
        catalog.countries()
    assert catalog.password is None
    assert not (paths.vendor_home() / "config.ini").exists()


def test_lists() -> None:
    """All list kinds are parsed and sorted."""
    catalog = logged_in()
    assert catalog.countries() == [("DE", "Germany"), ("US", "United States")]
    assert not (paths.vendor_home() / "config.ini").exists()
    assert ("Video Two", "DE") in catalog.streaming()
    assert [c.name for c in catalog.cities("de")] == ["Berlin", "Frankfurt"]
    assert catalog.cities("de")[1].servers == 2
    assert [s.name for s in catalog.servers("de", "Frankfurt")] == ["frankfurt-s01-i02",
                                                                    "frankfurt-s01-i01"]
    assert [s.name for s in catalog.servers("us", "New York", "Video One")] == ["newyork-s23-i12"]


def test_cache_and_refresh() -> None:
    """Valid entries avoid a call; fresh forces one."""
    catalog = logged_in()
    catalog.countries()
    count = len(system().calls)
    catalog.countries()
    assert len(system().calls) == count
    catalog.countries(fresh=True)
    assert len(system().calls) == count + 1


def test_old_list_beats_no_list() -> None:
    """A failed query falls back to the cached list."""
    catalog = logged_in()
    catalog.countries()
    system().vendor_output = "server trouble\n"
    assert catalog.countries(fresh=True)[0][0] == "DE"
    with pytest.raises(CgError, match="server trouble"):
        catalog.streaming()
    system().vendor_output = ""
    with pytest.raises(CgError, match="Exit 1"):
        catalog.cities("de")


def test_expired_cache_is_refetched() -> None:
    """An entry past its lifetime is queried again."""
    catalog = logged_in()
    catalog.countries()
    path = paths.cache_dir() / "countries.json"
    os.utime(path, (1, 1))
    path.write_text(json.dumps([["XX", "Old"]]), encoding="utf-8")
    os.utime(path, (1, 1))
    assert catalog.countries()[0][0] == "DE"


def test_missing_program() -> None:
    """A missing official program is named."""
    paths.vendor_binary().unlink()
    with pytest.raises(CgError, match="install.sh"):
        logged_in().countries()


def test_existing_client_login_is_kept() -> None:
    """The login file of an installed official client stays untouched."""
    home = paths.vendor_home()
    home.mkdir()
    text = f"[account]\nusername = me\npassword = {ACCOUNT_PASSWORD.replace('$', '$$')}\n"
    (home / "config.ini").write_text(text, encoding="utf-8")
    assert Catalog().countries()
    assert (home / "config.ini").read_text(encoding="utf-8") == text


def test_damaged_client_login_is_replaced() -> None:
    """An unreadable login file counts as absent."""
    home = paths.vendor_home()
    home.mkdir()
    (home / "config.ini").write_text("no section", encoding="utf-8")
    assert logged_in().countries()
