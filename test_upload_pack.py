from proxy import UploadPackHandler
import proxy
import os
clone_input = b'0098want 300a8ae00a1b532ed2364437273221e6c696e0c3 multi_ack_detailed no-done side-band-64k thin-pack ofs-delta deepen-since deepen-not agent=git/2.15.1\n0032want 388fd53133dd899d55d5bcd752840e0749d33d17\n0032want 8513c12068d96c9ba7f6e877f0d61210987634f3\n0032want 6659482901d79a4342c0522f78417d5985db535e\n0032want 2c103fdf7567b35216c9972c81489cbfa7935fc1\n00000009done\n'
creds = os.environ["CREDS"]

async def test_basic(tmpdir):
    proxy.workdir = str(tmpdir / "workdir")
    proc = UploadPackHandler("repo_test/manifest.git", creds)
    await proc.run(clone_input)
    full = b""
    ret = None
    while ret != b'':
        ret = await proc.read()
        full += ret
    assert len(full) > 0
    assert proc.error is None

async def test_unknown_want(tmpdir):
    proxy.workdir = str(tmpdir / "workdir")
    proc = UploadPackHandler("repo_test/manifest.git", creds)
    await proc.run(clone_input.replace(b"300a8ae00a1b532ed2364437273221e6c696e0c3", b"300a8ae00a1b532ed2364437273221e6c696e0c4"))
    assert proc.error is not None
    ret = await proc.read()
    assert b"ERR upload-pack: not our ref" in ret

