import os
import time

from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration

physx_license = """Copyright (c) 2019 NVIDIA Corporation. All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
 * Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.
 * Neither the name of NVIDIA CORPORATION nor the names of its
   contributors may be used to endorse or promote products derived
   from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""

class PhysXConan(ConanFile):
    name = "physx"
    description = "The NVIDIA PhysX SDK is a scalable multi-platform " \
                  "physics solution supporting a wide range of devices, " \
                  "from smartphones to high-end multicore CPUs and GPUs."
    license = "BSD-3-Clause"
    topics = ("conan", "PhysX", "physics")
    homepage = "https://github.com/NVIDIAGameWorks/PhysX"
    url = "https://github.com/conan-io/conan-center-index"
    exports_sources = ["CMakeLists.txt", "patches/**"]
    generators = "cmake"
    settings = "os", "compiler", "arch", "build_type"
    short_paths = True
    options = {
        "build_type": ["debug", "checked", "profile", "release"],
        "shared": [True, False],
        "enable_simd": [True, False],
        "enable_float_point_precise_math": [True, False],
        "fPIC": [True, False],
    }
    default_options = {
        "build_type": "release",
        "shared": True,
        "enable_simd": True,
        "enable_float_point_precise_math": False,
        "fPIC": True,
    }

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _build_subfolder(self):
        return "build_subfolder"

    def config_options(self):
        del self.options.fPIC # fpic is managed by physx build process (in physx/source/compiler/cmake/CMakeLists.txt)
        if self.settings.os != "Windows":
            del self.options.enable_float_point_precise_math
        if self.settings.os != "Windows" and self.settings.os != "Android":
            del self.options.enable_simd

    def configure(self):
        supported_os = ["Windows", "Linux", "Macos", "Android", "iOS"]
        os = str(self.settings.os)
        if os not in supported_os:
            raise ConanInvalidConfiguration("%s %s is not supported on %s" % (self.name, self.version, os))

        compiler = str(self.settings.compiler)
        if os == "Windows" and compiler != "Visual Studio":
            raise ConanInvalidConfiguration("%s %s does not support %s on %s" % (self.name, self.version, compiler, os))

        settings_build_type = str(self.settings.build_type)
        options_build_type = str(self.options.build_type)
        if options_build_type == "debug":
            if settings_build_type != "Debug":
                raise ConanInvalidConfiguration("Settings build_type=%s is not compatible " \
                                                "with physx:build_type=%s" % (settings_build_type, options_build_type))
        elif settings_build_type == "Debug":
            raise ConanInvalidConfiguration("Settings build_type=%s is not compatible " \
                                            "with physx:build_type=%s" % (settings_build_type, options_build_type))

        if compiler == "Visual Studio":
            if tools.Version(self.settings.compiler.version) < 9:
                raise ConanInvalidConfiguration("%s %s does not support Visual Studio < 9" % (self.name, self.version))

            runtime = str(self.settings.compiler.runtime)
            if options_build_type == "debug":
                if runtime != "MDd" and runtime != "MTd":
                    raise ConanInvalidConfiguration("Visual Studio Compiler runtime MDd or MTd " \
                                                    "is required when physx:build_type=%s" % options_build_type)
            elif runtime != "MD" and runtime != "MT":
                raise ConanInvalidConfiguration("Visual Studio Compiler runtime MD or MT " \
                                                "is required when physx:build_type=%s" % options_build_type)

    def package_id(self):
        self.info.settings.build_type = str(self.options.build_type)

    def source(self):
        tools.get(**self.conan_data["sources"][self.version])
        url = self.conan_data["sources"][self.version]["url"]
        extracted_dir = "PhysX-" + os.path.splitext(os.path.basename(url))[0]
        try:
            os.rename(extracted_dir, self._source_subfolder)
        except:
            # workaround for permission denied on windows
            time.sleep(10)
            os.rename(extracted_dir, self._source_subfolder)

    def build(self):
        for patch in self.conan_data["patches"][self.version]:
            tools.patch(**patch)
        cmake = self._configure_cmake()
        cmake.build()

    def _configure_cmake(self):
        cmake = CMake(self, build_type=str(self.options.build_type))

        # Options defined in physx/compiler/public/CMakeLists.txt
        cmake.definitions["TARGET_BUILD_PLATFORM"] = self._get_target_build_platform()
        cmake.definitions["PX_BUILDSNIPPETS"] = False
        cmake.definitions["PX_BUILDPUBLICSAMPLES"] = False
        cmake.definitions["PX_CMAKE_SUPPRESS_REGENERATION"] = False
        cmakemodules_path = os.path.join(
            self._source_subfolder,
            "externals",
            "CMakeModules" if self.settings.os == "Windows" else "cmakemodules"
        )
        cmake.definitions["CMAKEMODULES_PATH"] = os.path.abspath(cmakemodules_path).replace("\\", "/")
        cmake.definitions["PHYSX_ROOT_DIR"] = os.path.abspath(os.path.join(self._source_subfolder, "physx")).replace("\\", "/")

        # Options defined in physx/source/compiler/cmake/CMakeLists.txt
        if self.settings.os == "Windows" or self.settings.os == "Android":
            cmake.definitions["PX_SCALAR_MATH"] = not self.options.enable_simd # this value doesn't matter on other os
        cmake.definitions["PX_GENERATE_STATIC_LIBRARIES"] = not self.options.shared
        cmake.definitions["PX_EXPORT_LOWLEVEL_PDB"] = False
        cmake.definitions["PXSHARED_PATH"] = os.path.abspath(os.path.join(self._source_subfolder, "pxshared")).replace("\\", "/")
        cmake.definitions["PXSHARED_INSTALL_PREFIX"] = self.package_folder.replace("\\", "/")
        cmake.definitions["PX_GENERATE_SOURCE_DISTRO"] = False

        # Options defined in externals/cmakemodules/NVidiaBuildOptions.cmake
        cmake.definitions["NV_APPEND_CONFIG_NAME"] = False
        cmake.definitions["NV_USE_GAMEWORKS_OUTPUT_DIRS"] = False
        if self.settings.compiler == "Visual Studio":
            if self.settings.compiler.runtime == "MT":
                cmake.definitions["NV_USE_STATIC_WINCRT"] = True
                cmake.definitions["NV_USE_DEBUG_WINCRT"] = False
            elif self.settings.compiler.runtime == "MTd":
                cmake.definitions["NV_USE_STATIC_WINCRT"] = True
                cmake.definitions["NV_USE_DEBUG_WINCRT"] = True
            elif self.settings.compiler.runtime == "MDd":
                cmake.definitions["NV_USE_STATIC_WINCRT"] = False
                cmake.definitions["NV_USE_DEBUG_WINCRT"] = True
            else:
                cmake.definitions["NV_USE_STATIC_WINCRT"] = False
                cmake.definitions["NV_USE_DEBUG_WINCRT"] = False
        cmake.definitions["NV_FORCE_64BIT_SUFFIX"] = False
        cmake.definitions["NV_FORCE_32BIT_SUFFIX"] = False
        cmake.definitions["PX_ROOT_LIB_DIR"] = os.path.abspath(os.path.join(self.package_folder, "lib")).replace("\\", "/")

        if self.settings.os == "Windows":
            # Options defined in physx/source/compiler/cmake/windows/CMakeLists.txt
            cmake.definitions["PX_COPY_EXTERNAL_DLL"] = False # External dll copy disabled, PhysXDevice dll copy is handled afterward during conan packaging
            cmake.definitions["PX_FLOAT_POINT_PRECISE_MATH"] = self.options.enable_float_point_precise_math
            cmake.definitions["PX_USE_NVTX"] = False # Could be controlled by an option if NVTX had a recipe, disabled for the moment
            cmake.definitions["GPU_DLL_COPIED"] = True # PhysXGpu dll copy disabled, this copy is handled afterward during conan packaging

            # Options used in physx/source/compiler/cmake/windows/PhysX.cmake
            cmake.definitions["PX_GENERATE_GPU_PROJECTS"] = False

        cmake.configure(build_folder=self._build_subfolder)
        return cmake

    def _get_target_build_platform(self):
        return {
            "Windows" : "windows",
            "Linux" : "linux",
            "Macos" : "mac",
            "Android" : "android",
            "iOS" : "ios"
        }.get(str(self.settings.os))

    def package(self):
        cmake = self._configure_cmake()
        cmake.install()

        tools.save(os.path.join(self.package_folder, "licenses", "LICENSE"), physx_license)

        out_lib_dir = os.path.join(self.package_folder, "lib", str(self.options.build_type))
        self.copy(pattern="*.a", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.so", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.dylib*", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.lib", dst="lib", src=out_lib_dir, keep_path=False)
        self.copy(pattern="*.dll", dst="bin", src=out_lib_dir, keep_path=False)

        tools.rmdir(out_lib_dir)
        tools.rmdir(os.path.join(self.package_folder, "source"))

        self._copy_external_bin()

    def _copy_external_bin(self):
        if self.settings.os == "Linux" and self.settings.arch == "x86_64":
            external_bin_dir = os.path.join(self._source_subfolder, "physx", "bin", \
                                            "linux.clang", str(self.options.build_type))
            self.copy(pattern="*PhysXGpu*.so", dst="lib", src=external_bin_dir, keep_path=False)
        elif self.settings.os == "Windows" and self.settings.compiler == "Visual Studio":
            external_bin_subdir = "win.x86"
            if self.settings.arch == "x86":
                external_bin_subdir += "_32."
            elif self.settings.arch == "x86_64":
                external_bin_subdir += "_64."
            else:
                return

            version = tools.Version(self.settings.compiler.version)
            if version == "12":
                external_bin_dir = os.path.join(self._source_subfolder, "physx", "bin", \
                                                external_bin_subdir + "vc120.mt", str(self.options.build_type))
                self.copy(pattern="PhysXDevice*.dll", dst="bin", src=external_bin_dir, keep_path=False)
                self.copy(pattern="PhysXGpu*.dll", dst="bin", src=external_bin_dir, keep_path=False)
            elif version == "14":
                external_bin_dir = os.path.join(self._source_subfolder, "physx", "bin", \
                                                external_bin_subdir + "vc140.mt", str(self.options.build_type))
                self.copy(pattern="PhysXDevice*.dll", dst="bin", src=external_bin_dir, keep_path=False)
                self.copy(pattern="PhysXGpu*.dll", dst="bin", src=external_bin_dir, keep_path=False)
            elif version == "15":
                external_bin_dir = os.path.join(self._source_subfolder, "physx", "bin", \
                                                external_bin_subdir + "vc141.mt", str(self.options.build_type))
                self.copy(pattern="PhysXDevice*.dll", dst="bin", src=external_bin_dir, keep_path=False)
                external_bin_dir_140 = os.path.join(self._source_subfolder, "physx", "bin", \
                                                    external_bin_subdir + "vc140.mt", str(self.options.build_type))
                self.copy(pattern="PhysXGpu*.dll", dst="bin", src=external_bin_dir_140, keep_path=False)
            elif version >= "16":
                external_bin_dir = os.path.join(self._source_subfolder, "physx", "bin", \
                                                external_bin_subdir + "vc142.mt", str(self.options.build_type))
                self.copy(pattern="PhysXDevice*.dll", dst="bin", src=external_bin_dir, keep_path=False)
                external_bin_dir_140 = os.path.join(self._source_subfolder, "physx", "bin", \
                                                    external_bin_subdir + "vc140.mt", str(self.options.build_type))
                self.copy(pattern="PhysXGpu*.dll", dst="bin", src=external_bin_dir_140, keep_path=False)

    def package_info(self):
        self.cpp_info.libs = self._get_cpp_info_ordered_libs()
        self.output.info("LIBRARIES: %s" % self.cpp_info.libs)

        if self.settings.os == "Linux":
            self.cpp_info.system_libs.extend(["dl", "pthread", "rt"])
        elif self.settings.os == "Android":
            self.cpp_info.system_libs.append("log")

        self.cpp_info.defines = self._get_cpp_info_defines()
        self.cpp_info.cxxflags = self._get_cpp_info_cxxflags()

        self.cpp_info.name = "PhysX"

    def _get_cpp_info_ordered_libs(self):
        gen_libs = tools.collect_libs(self)

        # Libs ordered following linkage order:
        # - PhysX is a dependency of PhysXExtensions.
        # - PhysXPvdSDK is a dependency of PhysXExtensions, PhysX and PhysXVehicle.
        # - PhysXCommon is a dependency of PhysX and PhysXCooking.
        # - PhysXFoundation is a dependency of PhysXExtensions, PhysX, PhysXVehicle,
        #   PhysXPvdSDK, PhysXCooking, PhysXCommon and PhysXCharacterKinematic.
        # (- PhysXTask is a dependency of PhysX on Windows).
        lib_list = ["PhysXExtensions", "PhysX", "PhysXVehicle", "PhysXPvdSDK", \
                    "PhysXCooking", "PhysXCommon", "PhysXCharacterKinematic", \
                    "PhysXFoundation"]

        # List of lists, so if more than one matches the lib both will be added
        # to the list
        ordered_libs = [[] for _ in range(len(lib_list))]

        # The order is important, reorder following the lib_list order
        missing_order_info = []
        for real_lib_name in gen_libs:
            for pos, alib in enumerate(lib_list):
                if os.path.splitext(real_lib_name)[0].split("-")[0].endswith(alib):
                    ordered_libs[pos].append(real_lib_name)
                    break
            else:
                missing_order_info.append(real_lib_name)

        # Flat the list
        return [item for sublist in ordered_libs for item in sublist if sublist] + missing_order_info

    def _get_cpp_info_defines(self):
        defines = []
        if self.options.build_type == "debug":
            defines.extend(["PX_DEBUG=1", "PX_CHECHED=1"])
        elif self.options.build_type == "checked":
            defines.append("PX_CHECHED=1")
        elif self.options.build_type == "profile":
            defines.append("PX_PROFILE=1")

        if self.settings.os == "Windows":
            if self.options.shared:
                defines.extend([
                    "PX_PHYSX_CORE_EXPORTS",
                    "PX_PHYSX_COOKING_EXPORTS",
                    "PX_PHYSX_COMMON_EXPORTS",
                    "PX_PHYSX_FOUNDATION_EXPORTS"
                ])
            else:
                defines.append("PX_PHYSX_STATIC_LIB")
        elif self.settings.os == "Linux" and not self.options.shared:
            defines.append("PX_PHYSX_STATIC_LIB")

        return defines

    def _get_cpp_info_cxxflags(self):
        cxxflags = []
        if self.settings.compiler == "clang":
            cxxflags.append("-Wno-undef")

        return cxxflags
