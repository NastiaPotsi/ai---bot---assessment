from app.core.security import create_duplicate_key


def test_duplicate_key_is_deterministic_and_normalized():
    first = create_duplicate_key("secret", " John   Doe ", "ABC123")
    second = create_duplicate_key("secret", "john doe", "abc123")

    assert first == second


def test_duplicate_key_changes_with_secret():
    first = create_duplicate_key("secret-one", "John Doe", "1234")
    second = create_duplicate_key("secret-two", "John Doe", "1234")

    assert first != second

