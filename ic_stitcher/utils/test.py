import functools

def add_prefix_suffix(prefix: str, suffix: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if isinstance(result, str):
                return f"{prefix}{result}{suffix}"
            return result
        return wrapper
    return decorator

class Example:
    @add_prefix_suffix("Hello, ", "!")
    def greet(self, name):
        return name

example = Example()
print(example.greet("Vani"))  # Вывод: Hello, Alice!
