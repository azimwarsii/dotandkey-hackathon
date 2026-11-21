from deploy.start_api import seed_volume


def test_initial_seed_resumes_and_preserves_live_data(tmp_path):
    source = tmp_path / "seed"
    source.mkdir()
    (source / "market.sqlite3").write_bytes(b"snapshot")
    (source / "studio").mkdir()
    (source / "studio" / "demo.json").write_text("{}")

    volume = tmp_path / "data"
    volume.mkdir()
    (volume / ".seeding").touch()
    (volume / "market.sqlite3").write_bytes(b"live changes")
    (volume / "studio").mkdir()
    (volume / "studio" / "demo.json.seed-tmp").write_text("{")
    seed_volume(source, volume)

    assert (volume / "studio" / "demo.json").read_text() == "{}"
    assert (volume / "market.sqlite3").read_bytes() == b"live changes"
    assert (volume / ".seeded").is_file()
    (volume / "studio" / "demo.json").write_text("updated")
    seed_volume(source, volume)
    assert (volume / "studio" / "demo.json").read_text() == "updated"


def test_existing_unmarked_volume_is_left_intact(tmp_path):
    source = tmp_path / "seed"
    source.mkdir()
    (source / "market.sqlite3").write_bytes(b"seed")
    volume = tmp_path / "data"
    volume.mkdir()
    (volume / "user-content").touch()
    seed_volume(source, volume)
    assert not (volume / "market.sqlite3").exists()
    assert (volume / "user-content").is_file()
