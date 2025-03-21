import os
import re
import shlex
import subprocess
import sys
import sysconfig

import jinja2

# This caches the results of emsdk_environment.
emsdk_cache : dict[str, str] = { }

def emsdk_environment(c):
    """
    Loads the emsdk environment into `c`.
    """

    emsdk = c.path("{{ cross }}/emsdk")

    if not emsdk.exists():
        return

    if not emsdk_cache:

        env = dict(os.environ)
        env["EMSDK_BASH"] = "1"
        env["EMSDK_QUIET"] = "1"

        bash = subprocess.check_output([ str(emsdk), "construct_env" ], env=env, text=True)

        for l in bash.split("\n"):
            m = re.match(r'export (\w+)=\"(.*?)\";?$', l)
            if m:
                emsdk_cache[m.group(1)] = m.group(2)

    for k, v in emsdk_cache.items():
        c.env(k, v)


def llvm(c, bin="", prefix="", suffix="-15", clang_args="", use_ld=True):

    if bin and not bin.endswith("/"):
        bin += "/"

    c.var("llvm_bin", bin)
    c.var("llvm_prefix", prefix)
    c.var("llvm_suffix", suffix)

    ld = c.expand("{{llvm_bin}}lld{{llvm_suffix}}")

    if use_ld:
        clang_args = "-fuse-ld=lld -Wno-unused-command-line-argument " + clang_args

    if c.platform == "ios":
        c.var("cxx_clang_args", "-stdlib=libc++ -I{{cross}}/sdk/usr/include/c++")
    elif c.platform == "mac" or c.platform == "ios":
        c.var("cxx_clang_args", "-stdlib=libc++")
    else:
        c.var("cxx_clang_args", "")

    c.var("clang_args", clang_args)

    c.env("CC", "ccache {{llvm_bin}}{{llvm_prefix}}clang{{llvm_suffix}} {{ clang_args }} -std=gnu17")
    c.env("CXX", "ccache {{llvm_bin}}{{llvm_prefix}}clang++{{llvm_suffix}} {{ clang_args }} -std=gnu++17 {{ cxx_clang_args }}")
    c.env("CPP", "ccache {{llvm_bin}}{{llvm_prefix}}clang{{llvm_suffix}} {{ clang_args }} -E")

    # c.env("LD", "ccache " + ld)
    c.env("AR", "ccache {{llvm_bin}}llvm-ar{{llvm_suffix}}")
    c.env("RANLIB", "ccache {{llvm_bin}}llvm-ranlib{{llvm_suffix}}")
    c.env("STRIP", "ccache {{llvm_bin}}llvm-strip{{llvm_suffix}}")
    c.env("NM", "ccache {{llvm_bin}}llvm-nm{{llvm_suffix}}")
    c.env("READELF", "ccache {{llvm_bin}}llvm-readelf{{llvm_suffix}}")

    c.env("WINDRES", "{{llvm_bin}}{{llvm_prefix}}windres{{llvm_suffix}}")

    if c.platform == "windows":
        c.env("RC", "{{WINDRES}}")

def android_llvm(c, arch):

    if arch == "armv7a":
        eabi = "eabi"
    else:
        eabi = ""

    llvm(
        c,
        bin="{{cross}}/android-ndk-r25b/toolchains/llvm/prebuilt/linux-x86_64/bin",
        prefix=f"{arch}-linux-android{ eabi }21-",
        suffix="",
        clang_args="",
        use_ld=False,
    )

def build_environment(c):
    """
    Sets up the build environment inside the context.
    """

    if c.platform == "web" and c.kind not in ( "host",  "host-python", "cross" ):
        emsdk_environment(c)


    cpuccount = os.cpu_count()

    if cpuccount is None:
        cpuccount = 4

    if cpuccount > 12:
        cpuccount -= 4

    c.var("make", "nice make -j " + str(cpuccount))

    c.var("sysroot", c.tmp / f"sysroot.{c.platform}-{c.arch}")
    c.var("build_platform", sysconfig.get_config_var("HOST_GNU_TYPE"))

    c.env("CPPFLAGS", "-I{{ install }}/include")
    c.env("CFLAGS", "-O3 -I{{ install }}/include")
    c.env("LDFLAGS", "-O3 -L{{install}}/lib")

    c.env("PATH", "{{ host }}/bin:{{ PATH }}")

    if (c.platform == "linux") and (c.arch == "x86_64"):
        c.var("host_platform", "x86_64-pc-linux-gnu")
    elif (c.platform == "linux") and (c.arch == "aarch64"):
        c.var("host_platform", "aarch64-pc-linux-gnu")
    elif (c.platform == "linux") and (c.arch == "i686"):
        c.var("host_platform", "i686-pc-linux-gnu")
    elif (c.platform == "linux") and (c.arch == "armv7l"):
        c.var("host_platform", "arm-linux-gnueabihf")
    elif (c.platform == "windows") and (c.arch == "x86_64"):
        c.var("host_platform", "x86_64-w64-mingw32")
    elif (c.platform == "windows") and (c.arch == "i686"):
        c.var("host_platform", "i686-w64-mingw32")
    elif (c.platform == "mac") and (c.arch == "x86_64"):
        c.var("host_platform", "x86_64-apple-darwin14")
    elif (c.platform == "mac") and (c.arch == "arm64"):
        c.var("host_platform", "arm-apple-darwin21.6.0")
    elif (c.platform == "android") and (c.arch == "x86_64"):
        c.var("host_platform", "x86_64-linux-android")
    elif (c.platform == "android") and (c.arch == "arm64_v8a"):
        c.var("host_platform", "aarch64-linux-android")
    elif (c.platform == "android") and (c.arch == "armeabi_v7a"):
        c.var("host_platform", "armv7a-linux-androideabi")
    elif (c.platform == "ios") and (c.arch == "arm64"):
        c.var("host_platform", "arm-apple-darwin")
    elif (c.platform == "ios") and (c.arch == "armv7s"):
        c.var("host_platform", "arm-apple-darwin")
    elif (c.platform == "ios") and (c.arch == "sim-arm64"):
        c.var("host_platform", "arm-apple-darwin")
    elif (c.platform == "ios") and (c.arch == "sim-x86_64"):
        c.var("host_platform", "x86_64-apple-darwin")
    elif (c.platform == "web") and (c.arch == "wasm"):
        c.var("host_platform", "wasm32-unknown-emscripten")

    if (c.platform == "ios") and (c.arch == "arm64"):
        c.var("sdl_host_platform", "arm-ios-darwin21")
    elif (c.platform == "ios") and (c.arch == "armv7s"):
        c.var("sdl_host_platform", "arm-ios-darwin21")
    elif (c.platform == "ios") and (c.arch == "sim-arm64"):
        c.var("sdl_host_platform", "arm-ios-darwin21")
    elif (c.platform == "ios") and (c.arch == "sim-x86_64"):
        c.var("sdl_host_platform", "x86_64-ios-darwin21")
    else:
        c.var("sdl_host_platform", "{{ host_platform }}")

    if (c.platform == "ios") and (c.arch == "arm64"):
        c.var("ffi_host_platform", "aarch64-ios-darwin21")
    elif (c.platform == "ios") and (c.arch == "sim-arm64"):
        c.var("ffi_host_platform", "aarch64-ios-darwin21")
    elif (c.platform == "mac") and (c.arch == "arm64"):
        c.var("ffi_host_platform", "aarch64-apple-darwin21.6.0")
    else:
        c.var("ffi_host_platform", "{{ host_platform }}")

    if (c.platform == "ios") and (c.arch == "arm64"):
        c.env("IPHONEOS_DEPLOYMENT_TARGET", "13.0")
    elif (c.platform == "ios") and (c.arch == "armv7s"):
        c.env("IPHONEOS_DEPLOYMENT_TARGET", "13.0")
    elif (c.platform == "ios") and (c.arch == "sim-arm64"):
        c.env("IPHONEOS_DEPLOYMENT_TARGET", "13.0")
    elif (c.platform == "ios") and (c.arch == "sim-x86_64"):
        c.env("IPHONEOS_DEPLOYMENT_TARGET", "13.0")

    c.var("lipo", "llvm-lipo-15")


    if c.kind == "host" or c.kind == "host-python" or c.kind == "cross":

        llvm(c)
        c.env("LDFLAGS", "{{ LDFLAGS }} -L{{install}}/lib64")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "x86_64")

    elif (c.platform == "linux") and (c.arch == "x86_64"):

        llvm(c, clang_args="-target {{ host_platform }} --sysroot {{ sysroot }} -fPIC -pthread")
        c.env("LDFLAGS", "{{ LDFLAGS }} -L{{install}}/lib64")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "x86_64")

    elif (c.platform == "linux") and (c.arch == "aarch64"):

        llvm(c, clang_args="-target {{ host_platform }} --sysroot {{ sysroot }} -fPIC -pthread")
        c.env("LDFLAGS", "{{ LDFLAGS }} -L{{install}}/lib64")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "aarch64")

    elif (c.platform == "linux") and (c.arch == "i686"):

        llvm(c, clang_args="-target {{ host_platform }} --sysroot {{ sysroot }} -fPIC -pthread")
        c.env("LDFLAGS", "{{ LDFLAGS }} -L{{install}}/lib32")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "i386")

    elif (c.platform == "linux") and (c.arch == "armv7l"):

        llvm(c, clang_args="-target {{ host_platform }} --sysroot {{ sysroot }} -fPIC -pthread -mfpu=neon -mfloat-abi=hard")
        c.env("LDFLAGS", "{{ LDFLAGS }} -L{{install}}/lib32")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "armv7")

    elif (c.platform == "windows") and (c.arch == "x86_64"):

        llvm(
            c,
            bin="{{ cross }}/llvm-mingw/bin",
            prefix="x86_64-w64-mingw32-",
            suffix="",
            clang_args="-target {{ host_platform }} --sysroot {{ cross }}/llvm-mingw -fPIC -pthread",
            use_ld=False)

        c.var("cmake_system_name", "Windows")
        c.var("cmake_system_processor", "x86_64")

    elif (c.platform == "windows") and (c.arch == "i686"):

        llvm(
            c,
            bin="{{ cross }}/llvm-mingw/bin",
            prefix="i686-w64-mingw32-",
            suffix="",
            clang_args="-target {{ host_platform }} --sysroot {{ cross }}/llvm-mingw -fPIC -pthread",
            use_ld=False)

        c.var("cmake_system_name", "Windows")
        c.var("cmake_system_processor", "i386")

    elif (c.platform == "android") and (c.arch == "x86_64"):

        android_llvm(c, "x86_64")

        c.env("CFLAGS", "{{ CFLAGS }} -DSDL_MAIN_HANDLED")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "x86_64")

    elif (c.platform == "android") and (c.arch == "arm64_v8a"):

        android_llvm(c, "aarch64")

        c.env("CFLAGS", "{{ CFLAGS }} -DSDL_MAIN_HANDLED")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "aarch64")

    elif (c.platform == "android") and (c.arch == "armeabi_v7a"):

        android_llvm(c, "armv7a")

        c.env("CFLAGS", "{{ CFLAGS }} -DSDL_MAIN_HANDLED")

        c.var("cmake_system_name", "Linux")
        c.var("cmake_system_processor", "armv7")

    elif (c.platform == "mac") and (c.arch == "x86_64"):

        llvm(
            c,
            clang_args="-target x86_64-apple-darwin14 --sysroot {{cross}}/sdk",
        )

        c.env("MACOSX_DEPLOYMENT_TARGET", "10.10")
        c.env("CFLAGS", "{{ CFLAGS }} -mmacos-version-min=10.10")
        c.env("LDFLAGS", "{{ LDFLAGS }} -mmacos-version-min=10.10")

        c.var("cmake_system_name", "Darwin")
        c.var("cmake_system_processor", "x86_64")

    elif (c.platform == "mac") and (c.arch == "arm64"):

        llvm(
            c,
            clang_args="-target arm64-apple-macos11 --sysroot {{cross}}/sdk",
        )

        c.env("MACOSX_DEPLOYMENT_TARGET", "11.0")
        c.env("CFLAGS", "{{ CFLAGS }} -mmacos-version-min=11.0")
        c.env("LDFLAGS", "{{ LDFLAGS }} -mmacos-version-min=11.0")

        c.var("cmake_system_name", "Darwin")
        c.var("cmake_system_processor", "aarch64")

    elif (c.platform == "ios") and (c.arch == "arm64"):

        llvm(
            c,
            clang_args="-target arm64-apple-ios13.0 --sysroot {{cross}}/sdk",
        )

        c.env("CFLAGS", "{{ CFLAGS }} -DSDL_MAIN_HANDLED -miphoneos-version-min=13.0")
        c.env("LDFLAGS", "{{ LDFLAGS }} -miphoneos-version-min=13.0 -lmockrt")

        c.var("cmake_system_name", "Darwin")
        c.var("cmake_system_processor", "aarch64")

    elif (c.platform == "ios") and (c.arch == "sim-arm64"):

        llvm(
            c,
            clang_args="-target arm64-apple-ios13.0-simulator --sysroot {{cross}}/sdk",
        )

        c.env("CFLAGS", "{{ CFLAGS }} -DSDL_MAIN_HANDLED -mios-simulator-version-min=13.0")
        c.env("LDFLAGS", "{{ LDFLAGS }} -mios-version-min=13.0 -lmockrt")

        c.var("cmake_system_name", "Darwin")
        c.var("cmake_system_processor", "aarch64")

    elif (c.platform == "ios") and (c.arch == "sim-x86_64"):

        llvm(
            c,
            clang_args="-target x86_64-apple-ios13.0-simulator --sysroot {{cross}}/sdk",
        )

        c.env("CFLAGS", "{{ CFLAGS }} -DSDL_MAIN_HANDLED -mios-simulator-version-min=13.0")
        c.env("LDFLAGS", "{{ LDFLAGS }} -mios-simulator-version-min=13.0 -lmockrt")

        c.var("cmake_system_name", "Darwin")
        c.var("cmake_system_processor", "x86_64")

    elif (c.platform == "web") and (c.arch == "wasm") and (c.name != "web"):

        c.env("CFLAGS", "{{ CFLAGS }} -O3 -sUSE_SDL=2 -sUSE_LIBPNG -sUSE_LIBJPEG=1 -sUSE_BZIP2=1 -sUSE_ZLIB=1")
        c.env("LDFLAGS", "{{ LDFLAGS }} -O3 -sUSE_SDL=2 -sUSE_LIBPNG -sUSE_LIBJPEG=1 -sUSE_BZIP2=1 -sUSE_ZLIB=1 -sEMULATE_FUNCTION_POINTER_CASTS=1")

        c.var("emscriptenbin", "{{ cross }}/upstream/emscripten")
        c.var("crossbin", "{{ cross }}/upstream/emscripten")

        c.env("CC", "ccache {{ emscriptenbin }}/emcc")
        c.env("CXX", "ccache {{ emscriptenbin }}/em++")
        c.env("CPP", "ccache {{ emscriptenbin }}/emcc -E")
        c.env("LD", "ccache {{ emscriptenbin }}/emcc")
        c.env("LDSHARED", "ccache {{ emscriptenbin }}/emcc")
        c.env("AR", "ccache {{ emscriptenbin }}/emar")
        c.env("RANLIB", "ccache {{ emscriptenbin }}/emranlib")
        c.env("STRIP", "ccache  {{ emscriptenbin }}/emstrip")
        c.env("NM", "{{ crossbin}}/llvm-nm")

        c.env("EMSCRIPTEN_TOOLS", "{{emscriptenbin}}/tools")
        c.env("EMSCRIPTEN", "{{emscriptenbin}}")

        c.env("PKG_CONFIG_LIBDIR", "{{cross}}/upstream/emscripten/cache/sysroot/lib/pkgconfig:{{cross}}/upstream/emscripten/system/lib/pkgconfig")

        # Used to find sdl2-config.
        c.env("PATH", "{{cross}}/upstream/emscripten/system/bin/:{{PATH}}")

        c.var("cmake_system_name", "Emscripten")
        c.var("cmake_system_processor", "generic")


    c.env("PKG_CONFIG_PATH", "{{ install }}/lib/pkgconfig")
    c.env("PKG_CONFIG", "pkg-config --static")

    c.env("CFLAGS", "{{ CFLAGS }} -DRENPY_BUILD")
    c.env("CXXFLAGS", "{{ CFLAGS }}")

    c.var("cmake", "cmake -DCMAKE_SYSTEM_NAME={{ cmake_system_name }} -DCMAKE_SYSTEM_PROCESSOR={{ cmake_system_processor }} -DCMAKE_BUILD_TYPE=Release")

    # Used by zlib.
    if c.kind != "host":
        c.var("cross_config", "--host={{ host_platform }} --build={{ build_platform }}")
        c.var("sdl_cross_config", "--host={{ sdl_host_platform }} --build={{ build_platform }}")
        c.var("ffi_cross_config", "--host={{ ffi_host_platform }} --build={{ build_platform }}")


def run(command, context, verbose=False, quiet=False):
    args = shlex.split(command)

    if verbose:
        print(" ".join(shlex.quote(i) for i in args))

    if not quiet:
        p = subprocess.run(args, cwd=context.cwd, env=context.environ)
    else:
        with open("/dev/null", "w") as f:
            p = subprocess.run(args, cwd=context.cwd, env=context.environ, stdout=f, stderr=f)

    if p.returncode != 0:
        print(f"{context.task_name}: process failed with {p.returncode}.")
        print("args:", args)
        import traceback
        traceback.print_stack()
        sys.exit(1)

class RunCommand(object):

    def __init__(self, command, context):
        command = context.expand(command)
        self.command = shlex.split(command)

        self.cwd = context.cwd
        self.environ = context.environ.copy()

        self.p = subprocess.Popen(self.command, cwd=self.cwd, env=self.environ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")

    def wait(self):
        self.code = self.p.wait()
        self.output = self.p.stdout.read() # type: ignore

    def report(self):
        print ("-" * 78)

        for i in self.command:
            if " " in i:
                print(repr(i), end=" ")
            else:
                print(i, end=" ")

        print()
        print()
        print(self.output)

        if self.code != 0:
            print()
            print(f"Process failed with {self.code}.")

class RunGroup(object):

    def __init__(self, context):
        self.context = context
        self.tasks = [ ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return

        for i in self.tasks:
            i.wait()

        good = [ i for i in self.tasks if i.code == 0 ]
        bad = [ i for i in self.tasks if i.code != 0 ]

        for i in good:
            i.report()

        for i in bad:
            i.report()

        if bad:
            print()
            print("{} tasks failed.".format(len(bad)))
            sys.exit(1)

    def run(self, command):
        self.tasks.append(RunCommand(command, self.context))
