import subprocess
import proxy
from proxy import find_gitpath, find_directory
from py.path import local
def test_find_gitpath(tmpdir):
    proxy.workdir = str(tmpdir)
    assert find_gitpath("/repo_test/manifest/info/refs") == "repo_test/manifest.git"
    assert find_gitpath("/repo_test/manifest.git/info/refs") == "repo_test/manifest.git"
    assert find_gitpath("/repo_test/manifest.git/git-upload-pack") ==  "repo_test/manifest.git"

def test_find_directory(tmpdir):
    proxy.workdir = str(tmpdir)
    assert local(find_directory("repo_test/manifest.git")).check(dir=True)
