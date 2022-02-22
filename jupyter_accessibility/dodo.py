from rich import print
from pathlib import Path
from functools import wraps, partial
from importlib.metadata import distribution
from dataclasses import dataclass
from appdirs import user_data_dir
from doit import create_after, task_params
from os import environ

DOIT_CONFIG = dict(verbosity=2)

HERE = Path()
THIS = Path(__file__).parent
NOXFILE = THIS / "noxfile.py"
NOX = Path(".nox")
REPOS = [
    "https://github.com/jupyterlab/lumino",
    "https://github.com/jupyterlab/jupyterlab",
    # "https://github.com/jupyterlab/retrolab",
]
from doit import create_after
from doit.tools import CmdAction as Action, config_changed, create_folder


def write(file, content):
    Path(file).write_text(content)


def is_installed(x):
    try:
        return distribution(x) and True
    except:
        return False


def requires(x):
    return dict(
        name=f"install",
        actions=[f"pip install {x}"],
        uptodate=list(map(is_installed, x.split())),
    )


def rmdir(*dir):
    from shutil import rmtree

    for dir in dir:
        rmtree(dir, True)
        print(f"removed directory: {dir}")


def task_env(name="build"):
    PREFIX = HERE / name / ".env"
    yield dict(
        name="conda",
        actions=[
            f'conda create -yc conda-forge --prefix {PREFIX} python=3.9 "nodejs>=14,<15" yarn git'
        ],
        uptodate=[PREFIX.exists()],
        clean=[(rmdir, [PREFIX])],
    )


@create_after("env")
def task_lumino(repo="https://github.com/jupyterlab/lumino", dir=HERE / "build"):
    repo = Repo(url=repo, dir=dir)
    print(repo)
    from json import loads

    yield get_clone_task(repo.url, repo.path, repo.env)
    print(repo)
    yield dict(
        name=f"install:yarn",
        file_dep=[repo.package, repo.head],
        actions=[(create_folder, [repo.links]), do(*repo.yarn, cwd=repo.path)],
        targets=[repo.yarn_integrity],
        task_dep=["lumino:clone"],
    )

    for pkg_json in repo.get_packages():
        pkg = pkg_json.parent
        pkg_data = loads(pkg_json.read_text(encoding="utf-8"))
        pkg_name = pkg_data["name"]
        out_link = repo.links / pkg_data["name"] / "package.json"

        # only set lumino out links
        yield dict(
            name=f"link:out:{pkg_name}",
            file_dep=[repo.yarn_integrity, pkg_json],
            actions=[(create_folder, [repo.links]), do(*repo.yarn, "link", cwd=pkg)],
            targets=[out_link],
            task_dep=["lumino:install:yarn"],
        )


@create_after("env")
def task_jupyterlab(
    repo="https://github.com/jupyterlab/jupyterlab", dir=HERE / "build"
):
    repo = Repo(url=repo, dir=dir)
    print(repo)
    from json import loads

    yield get_clone_task(repo.url, repo.path, repo.env)
    yield dict(
        name="install:pip",
        file_dep=[repo.package, repo.head],
        actions=[do(F"{repo.conda} pip install -e.", cwd=repo.path)]
    )
    yield dict(
        name=f"install:yarn",
        file_dep=[repo.package, repo.head],
        actions=[(create_folder, [repo.links]), do(*repo.yarn, cwd=repo.path)],
        targets=[repo.yarn_integrity],
        task_dep=["jupyterlab:clone"],
    )

    for pkg_json in repo.get_packages():
        pkg = pkg_json.parent
        pkg_data = loads(pkg_json.read_text(encoding="utf-8"))
        pkg_name = pkg_data["name"]
        out_link = repo.links / pkg_data["name"] / "package.json"

        # set lumino in links and jupyterlab out links


@dataclass
class Repo:
    url: str

    dir: Path = HERE / "build"
    name: str = None
    env: Path = None
    path: Path = None
    head: Path = None
    package: Path = None
    links: Path = None
    yarn: Path = None
    setup: Path = None

    def __post_init__(self):
        self.name = get_name(self.url)
        self.path = self.dir / self.name
        self.head = self.path / ".git" / "HEAD"
        self.package = self.path / "package.json"
        self.links = (self.dir / "repos" / ".yarn-links").resolve()
        self.env = (self.dir / ".env").resolve()
        self.conda = [            "conda",
            "run",
            "--prefix",
            self.env]
        self.yarn = self.conda + [

            "yarn",
            "--link-folder",
            self.links,
        ]
        self.yarn_integrity = self.path / "node_modules" / ".yarn-integrity"
        self.setup = self.path / "setup.py"

    def get_packages(self, where="packages"):
        yield from (self.path / where).glob("*/package.json")


def get_name(id):
    return id.rpartition("/")[2]


def get_clone_task(repo, target, prefix, depth=1):
    name = get_name(repo)
    HEAD = target / ".git" / "HEAD"
    return dict(
        name=f"clone",
        actions=[
            (create_folder, [target]),
            f"""conda run --prefix { prefix} git clone --depth {depth} {repo} {target}""",
        ],
        targets=[HEAD],
        uptodate=[HEAD.exists()],
    )


ENV = dict(
    NODE_OPTS="--max-old-space-size=4096",
    PIP_DISABLE_PIP_VERSION_CHECK="1",
    PIP_IGNORE_INSTALLED="1",
    PIP_NO_BUILD_ISOLATION="1",
    PIP_NO_DEPENDENCIES="1",
    PYTHONIOENCODING="utf-8",
    PYTHONUNBUFFERED="1",
)


def do(*args, cwd=THIS, **kwargs):
    """wrap a Action for consistency"""
    if len(args) == 1:
        args = args[0].split()
    kwargs.setdefault("env", {})
    kwargs["env"] = environ
    kwargs["env"].update(ENV)
    print(args, kwargs, cwd)
    return Action(
        list(map(str, args)), shell=False, cwd=str(Path(cwd).resolve()), **kwargs
    )
