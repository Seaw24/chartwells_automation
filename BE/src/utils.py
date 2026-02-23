import unicodedata


# strips accents from a string, used for matching location names in the cash sheet filling process
def strip_accents(text):
    nfkd = unicodedata.normalize("NFKD", text)
    return ''.join(c for c in nfkd if unicodedata.category(c) != 'Mn').strip()
