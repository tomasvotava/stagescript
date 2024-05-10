from slugify import slugify

from stagescript.naming import get_random_name, get_random_slug


def test_random_names_generator() -> None:
    # Wonder if this ever fails
    names = {get_random_name() for _ in range(50)}
    assert len(names) == 50


def test_random_slug_generator() -> None:
    for _ in range(1000):
        slug = get_random_slug()
        assert slug == slugify(slug)
