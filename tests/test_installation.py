from importlib.metadata import metadata


def test_installed_project_metadata():
    project = metadata("pai-discord")
    assert project["Name"] == "pai-discord"
    assert project["Requires-Python"] == ">=3.12"
