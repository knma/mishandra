from types import SimpleNamespace

colored = SimpleNamespace(
  none = lambda x: x,
  red = lambda x: f"\x1b[31m{x}\x1b[0m",
  green = lambda x: f"\x1b[32m{x}\x1b[0m",
  yellow = lambda x: f"\x1b[33m{x}\x1b[0m",
  blue = lambda x: f"\x1b[34m{x}\x1b[0m",
  magenta = lambda x: f"\x1b[35m{x}\x1b[0m",
  cyan = lambda x: f"\x1b[36m{x}\x1b[0m",
  gray = lambda x: f"\x1b[90m{x}\x1b[0m",
)

decorated =  SimpleNamespace(
  bold = lambda x: f"\u001b[1m{x}\u001b[0m",
)