cmake_minimum_required(VERSION 3.16)
project(arb-core VERSION 0 LANGUAGES C)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR "arb-core targets Linux")
endif()

set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

add_compile_definitions(_GNU_SOURCE)
add_compile_options(-Wall -Wextra -Wpedantic -Werror)

if(CMAKE_BUILD_TYPE STREQUAL "Release")
    add_compile_options(-O3 -march=native -mtune=native)
endif()

include_directories(${CMAKE_SOURCE_DIR}/include)

add_library(core OBJECT src/classify.c src/tx.c src/pool.c src/dex/meteora_dlmm.c src/dex/dlmm_cache.c src/dex/pump.c src/cycle.c)
set_property(TARGET core PROPERTY C_EXTENSIONS ON)
target_compile_options(core PRIVATE -Wno-pedantic)

add_executable(replay tests/replay.c $<TARGET_OBJECTS:core>)
add_executable(build_pools tests/build_pools.c $<TARGET_OBJECTS:core>)
add_executable(core001 tests/core001.c $<TARGET_OBJECTS:core>)
add_executable(core002 tests/core002.c $<TARGET_OBJECTS:core>)
add_executable(core003 tests/core003.c $<TARGET_OBJECTS:core>)
set_property(TARGET core003 PROPERTY C_EXTENSIONS ON)
target_compile_options(core003 PRIVATE -Wno-pedantic)

add_executable(core004 tests/core004.c $<TARGET_OBJECTS:core>)
set_property(TARGET core004 PROPERTY C_EXTENSIONS ON)
target_compile_options(core004 PRIVATE -Wno-pedantic)

add_executable(core005 tests/core005.c $<TARGET_OBJECTS:core>)
set_property(TARGET core005 PROPERTY C_EXTENSIONS ON)
target_compile_options(core005 PRIVATE -Wno-pedantic)

add_executable(core006 tests/core006.c $<TARGET_OBJECTS:core>)
set_property(TARGET core006 PROPERTY C_EXTENSIONS ON)
target_compile_options(core006 PRIVATE -Wno-pedantic)

add_executable(core007 tests/core007.c $<TARGET_OBJECTS:core>)
set_property(TARGET core007 PROPERTY C_EXTENSIONS ON)
target_compile_options(core007 PRIVATE -Wno-pedantic)

add_executable(core008 tests/core008.c $<TARGET_OBJECTS:core>)
set_property(TARGET core008 PROPERTY C_EXTENSIONS ON)
target_compile_options(core008 PRIVATE -Wno-pedantic)
