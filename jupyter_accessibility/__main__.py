if __name__ == "__main__":
    from sys import argv

    from doit.cmd_base import ModuleTaskLoader
    from doit.doit_cmd import DoitMain

    from . import dodo

    DoitMain(ModuleTaskLoader(dodo)).run(argv[1:])
