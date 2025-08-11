::_release.bat

set "VERSION=%~1"

git tag -a v%VERSION% -m "v%VERSION%"
git push origin v%VERSION%
