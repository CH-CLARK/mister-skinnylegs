import datetime
import json
import sys
import pathlib
import typing
import collections.abc as colabc
import asyncio
from util.plugin_loader import PluginLoader
from util.artifact_utils import ArtifactResult, ArtifactSpec
from util.fs_utils import sanitize_filename

from ccl_chromium_reader import ChromiumProfileFolder

__version__ = "0.0.3"
__description__ = "Library for reading Chrome/Chromium Cache (both blockfile and simple format)"
__contact__ = "Alex Caithness"

PLUGIN_PATH = pathlib.Path(__file__).resolve().parent / pathlib.Path("plugins")

BANNER = """
╔╦╗┬┌─┐┌┬┐┌─┐┬─┐            
║║║│└─┐ │ ├┤ ├┬┘            
╩ ╩┴└─┘ ┴ └─┘┴└─            
╔═╗┬┌─┬┌┐┌┌┐┌┬ ┬┬  ┌─┐┌─┐┌─┐
╚═╗├┴┐│││││││└┬┘│  ├┤ │ ┬└─┐
╚═╝┴ ┴┴┘└┘┘└┘ ┴ ┴─┘└─┘└─┘└─┘
"""


class MisterSkinnylegs:
    def __init__(
            self,
            plugin_path: pathlib.Path,
            profile_path: pathlib.Path,
            log_callback: typing.Optional[colabc.Callable[[str], None]]=None):
        self._plugin_loader = PluginLoader(plugin_path)

        if not profile_path.is_dir():
            raise NotADirectoryError(profile_path)

        self._profile_folder_path = profile_path

        self._log_callback = log_callback or MisterSkinnylegs.log_fallback

    async def _run_artifact(self, spec: ArtifactSpec):
        with ChromiumProfileFolder(self._profile_folder_path) as profile:
            result = spec.function(profile, self._log_callback)
            return spec, {
                "artifact_service": spec.service,
                "artifact_name": spec.name,
                "artifact_version": spec.version,
                "artifact_description": spec.description,
                "result": result.result}

    async def run_all(self):
        tasks = (self._run_artifact(spec) for spec, path in self.artifacts)
        for coro in asyncio.as_completed(tasks):
            yield await coro

    async def run_one(self, artifact_name: str):
        spec, path = self._plugin_loader[artifact_name]
        result = self._run_artifact(spec)
        return spec, result

    @property
    def artifacts(self) -> colabc.Iterable[tuple[ArtifactSpec, pathlib.Path]]:
        yield from self._plugin_loader.artifacts

    @property
    def profile_folder(self) -> pathlib.Path:
        return self._profile_folder_path

    @staticmethod
    def log_fallback(message: str):
        print(f"Log:\t{message}")


class SimpleLog:
    def __init__(self, out_path: pathlib.Path):
        self._f = out_path.open("xt", encoding="utf-8")

    def log_message(self, message: str):
        formatted_message = f"{datetime.datetime.now()}\t{message.replace('\n', '\n\t')}"
        self._f.write(formatted_message)
        self._f.write("\n")

        print(formatted_message.encode(sys.stdout.encoding, "replace").decode(sys.stdout.encoding))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._f.close()


async def main(args):
    profile_input_path = pathlib.Path(args[0])
    report_out_folder_path = pathlib.Path(args[1])

    print(BANNER)

    if not profile_input_path.is_dir():
        raise NotADirectoryError(f"Profile folder {profile_input_path} does not exist or is not a directory")

    if report_out_folder_path.exists():
        raise FileExistsError(f"Output folder {report_out_folder_path} already exists")

    report_out_folder_path.mkdir(parents=True)
    log_file = SimpleLog(report_out_folder_path / f"log_{datetime.datetime.now():%Y%m%d_%H%M%S}.log")
    log = log_file.log_message

    mr_sl = MisterSkinnylegs(PLUGIN_PATH, profile_input_path, log_callback=log)

    log(f"Mister Skinnylegs v{__version__} is on the go!")
    log(f"Working with profile folder: {mr_sl.profile_folder}")
    log("")

    log("Plugins loaded:")
    log("===============")
    for spec, path in mr_sl.artifacts:
        log(f"{spec.name}  -  {path.name}")

    log("")
    log("Processing starting...")

    async for spec, result in mr_sl.run_all():
        log(f"Results acquired for {spec.name}")
        if not result["result"]:
            log(f"{spec.name} had not results, skipping")
            continue

        out_dir_path = report_out_folder_path / sanitize_filename(spec.service)
        out_dir_path.mkdir(exist_ok=True)
        out_file_path = out_dir_path / (sanitize_filename(spec.name) + ".json")

        log(f"Generating output at {out_file_path}")

        with out_file_path.open("xt", encoding="utf-8") as out:
            json.dump(result, out)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
