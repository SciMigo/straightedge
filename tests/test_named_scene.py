"""A caller can name the scene file, so two renders can share a directory.

``write_scene`` wrote ``scene.py`` unconditionally, so two renders pointed at one
``output_dir`` overwrote each other silently — the collision a concurrent caller
hits. A distinct ``name`` per render keeps them apart, and the render path already
keys off the file's stem, so nothing downstream needs telling.
"""

from __future__ import annotations

from straightedge import build_plan
from straightedge.renderer import write_scene


def test_default_name_is_unchanged(tmp_path):
    path = write_scene(build_plan("画一个椭圆"), tmp_path)
    assert path.name == "scene.py"


def test_a_name_sets_the_file_stem(tmp_path):
    path = write_scene(build_plan("画一个椭圆"), tmp_path, name="render_042")
    assert path.name == "render_042.py"
    assert path.exists()


def test_two_names_in_one_dir_do_not_collide(tmp_path):
    a = write_scene(build_plan("画一个椭圆"), tmp_path, name="a")
    b = write_scene(build_plan("画 y=x^2 的导数"), tmp_path, name="b")
    assert a != b
    assert a.exists() and b.exists()
    # Each file is its own scene, not the last one written over both.
    assert a.read_text() != b.read_text()
