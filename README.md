# git-proxy

A git+http(s) proxy for optimising git server usage.

- Fully stateless for horizontal scalability

- Supports BasicAuth authentication (auth check is made by forcing a call to upstream, by reusing the BasicAuth creds)

- List of refs is always re-fetched from upstream (first step of the git+http(s) protocol)
    - with gitlab and gitaly, this should not be a problem as gitaly is supposed to cache that result.

- git-uploadpack part is always tried locally first, which greatly reduce the load on upstream, as uploadpack is typically not cacheable.

- Only supports http(s) and basicAuth. Doing similar proxy with ssh is much harder, because of the authentication check. SSH is not allowing MITM auth.

- Tested with gitlab-ce 11.2, but should work with any BasicAuth git+http(s) server

# Dev

    pipenv install --dev
    export GITSERVER_UPSTREAM=http://gitlab.mycompany.com/ WORKING_DIRECTORY=~/git-proxy CREDS=gitlab-ci-token:<GITLAB_TOKEN>

    pipenv run pytest  # at the moment the tests are dependent on test repositories available on my company's gitlab. Sorry.
    pipenv run adev runserver --livereload proxy.py

# Prod
    # no needs creds for prod, only for tests
    GITSERVER_UPSTREAM=http://gitlab.mycompany.com/ WORKING_DIRECTORY=~/git-proxy pipenv run python proxy.py

# License 

MIT