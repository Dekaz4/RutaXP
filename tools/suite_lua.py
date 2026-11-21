"""Bind an embedded WoW Lua chunk to its native addon namespace."""

import re


# The installation templates and both release builders ship exactly this
# first-party runtime. Native modules are added only to the personal package.
SUITE_FILES = ("RutaXP.toc", "TalentCore.lua", "Talents.lua", "TalentBuilds.lua",
               "Suite.lua", "WorldMapTracking.lua", "WorldMapServiceData.lua",
               "WorldMapServices.lua", "WorldMapQuestTracking.lua")


# These are the only tokens needed to distinguish a chunk's varargs from a
# function's. A long string or comment, including an entire RestedXP guide,
# is consumed in one step without interpreting what it contains.
_TOKENS = re.compile(r"""--|["']|\[(=*)\[|\.\.\.|\b(?:if|do|repeat|function|end|until)\b""", re.ASCII)
_LONG_OPEN = re.compile(r"\[(=*)\[")
_LINE_END = re.compile(r"[\r\n]")


def _after_quote(text, start):
    quote = text[start]
    while True:
        close = text.find(quote, start + 1)
        if close < 0:
            return len(text)
        preceding = close - 1
        while text[preceding] == "\\":
            preceding -= 1
        if (close - preceding - 1) % 2 == 0:
            return close + 1
        start = close


def _after_long(text, opener):
    delimiter = "]" + opener[1] + "]"
    close = text.find(delimiter, opener.end())
    return len(text) if close < 0 else close + len(delimiter)


def bind_namespace(module, relpath, text):
    """Route top-level ... to the module without adding locals or a wrapper.

    Lua 5.1 gives nested vararg functions an implicit arg local. Adding even
    one local to a native chunk can exceed the 200-local limit in OpenMap.
    Return the original text verbatim when no substitutions are needed.
    """
    if "..." not in text:
        return text
    if not re.fullmatch(r"[A-Za-z0-9_]+", module):
        raise ValueError(f"Invalid addon name for {relpath}")
    parts, blocks = [], []
    pos = copied = functions = 0
    while match := _TOKENS.search(text, pos):
        value = match[0]
        pos = match.end()
        if value == "--":
            opener = _LONG_OPEN.match(text, pos)
            if opener:
                pos = _after_long(text, opener)
            else:
                eol = _LINE_END.search(text, pos)
                pos = eol.end() if eol else len(text)
        elif value in ('"', "'"):
            pos = _after_quote(text, match.start())
        elif value.startswith("["):
            pos = _after_long(text, match)
        elif value == "...":
            if functions == 0:
                parts.extend((text[copied:match.start()], f'RutaXPModuleContext("{module}")'))
                copied = pos
        elif value in ("end", "until"):
            if blocks and blocks.pop() == "function":
                functions -= 1
        else:
            blocks.append(value)
            if value == "function":
                functions += 1
    if not parts:
        return text
    parts.append(text[copied:])
    return "".join(parts)
