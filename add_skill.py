import sys

filepath = sys.argv[1]
with open(filepath, 'r') as f:
    content = f.read()

target = """\\cvachievement{\\faCode}{Organisation \\& Rigueur}{Respect des procédures d'hygiène/sécurité, ponctualité, polyvalence caisse/rayon}
\\par"""
new_content = """\\cvachievement{\\faCode}{Organisation \\& Rigueur}{Respect des procédures d'hygiène/sécurité, ponctualité, polyvalence caisse/rayon}
\\par\\vspace{0.2em}
\\cvachievement{\\faDesktop}{Outil Informatique \& Maintenance}{Maîtrise du Pack Office, montage matériel PC, installation OS (Windows, Linux, macOS), et dépannage logiciel/matériel général}
\\par"""

content = content.replace(target, new_content)

with open(filepath, 'w') as f:
    f.write(content)
