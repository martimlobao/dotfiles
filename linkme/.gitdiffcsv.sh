#!/bin/sh
# Used as diff driver "command" so that `git diff file.csv` uses word-diff.
# Receives: path old-file old-hex old-mode new-file new-hex new-mode
# Ignore attributes in child so *.csv temp paths don't re-trigger this driver; use word-diff-regex=. explicitly.
# Run diff; then exit 0 so parent git does not treat "files differ" (exit 1) as "diff died".
# Include "not comma or newline" so the final field is a word when there is no trailing newline.
# In POSIX ERE, \n inside bracket expressions is literal (backslash + 'n'), so use a real newline.
nl='
'
git -c core.attributesFile=/dev/null diff --no-index --word-diff --word-diff-regex="[^,${nl}]+[,${nl}]|[^,${nl}]+$|[,]" "$2" "$5"
exit 0
