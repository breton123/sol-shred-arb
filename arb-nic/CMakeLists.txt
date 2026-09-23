cmake_minimum_required(VERSION 3.16)
project(arb-nic VERSION 0 LANGUAGES C)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
    message(FATAL_ERROR "arb-nic v0 targets Linux")
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

add_executable(txgen src/txgen.c)
add_executable(rxbench src/rxbench.c)
add_executable(replay_rx src/replay_rx.c)

find_program(CLANG_EXECUTABLE NAMES clang clang-18 clang-17 clang-16)
find_library(LIBBPF_LIBRARY NAMES bpf libbpf.so.1
    PATHS /usr/lib/x86_64-linux-gnu /usr/lib64 /usr/lib
    NO_DEFAULT_PATH
)
if(NOT LIBBPF_LIBRARY)
    foreach(_so IN ITEMS
        /usr/lib/x86_64-linux-gnu/libbpf.so.1
        /usr/lib64/libbpf.so.1
        /usr/lib/libbpf.so.1
        /usr/lib/x86_64-linux-gnu/libbpf.so)
        if(EXISTS ${_so})
            set(LIBBPF_LIBRARY ${_so})
            break()
        endif()
    endforeach()
endif()
find_library(LIBELF_LIBRARY NAMES elf libelf.so.1
    PATHS /usr/lib/x86_64-linux-gnu /usr/lib64 /usr/lib
)
if(NOT LIBELF_LIBRARY AND EXISTS /usr/lib/x86_64-linux-gnu/libelf.so.1)
    set(LIBELF_LIBRARY /usr/lib/x86_64-linux-gnu/libelf.so.1)
endif()
find_library(LIBZ_LIBRARY NAMES z)

if(CLANG_EXECUTABLE AND LIBBPF_LIBRARY)
    set(XDP_BPF_O ${CMAKE_BINARY_DIR}/xdp.bpf.o)
    set(BPF_ARCH_INCLUDE)
    if(EXISTS /usr/include/x86_64-linux-gnu)
        list(APPEND BPF_ARCH_INCLUDE -I/usr/include/x86_64-linux-gnu)
    endif()
    add_custom_command(
        OUTPUT ${XDP_BPF_O}
        COMMAND ${CLANG_EXECUTABLE}
            --target=bpf
            -O2 -g -Wall
            ${BPF_ARCH_INCLUDE}
            -I${CMAKE_SOURCE_DIR}/include
            -I${CMAKE_SOURCE_DIR}/bpf/include
            -c ${CMAKE_SOURCE_DIR}/bpf/xdp.bpf.c
            -o ${XDP_BPF_O}
        DEPENDS
            ${CMAKE_SOURCE_DIR}/bpf/xdp.bpf.c
            ${CMAKE_SOURCE_DIR}/include/xdp_port.h
            ${CMAKE_SOURCE_DIR}/bpf/include/bpf/bpf_helpers.h
            ${CMAKE_SOURCE_DIR}/bpf/include/bpf/bpf_endian.h
        COMMENT "Building XDP BPF object"
        VERBATIM
    )
    add_custom_target(xdp_bpf ALL DEPENDS ${XDP_BPF_O})

    add_executable(xdpctl src/xdpctl.c)
    add_executable(xskbench src/xskbench.c)
    add_dependencies(xdpctl xdp_bpf)
    add_dependencies(xskbench xdp_bpf)
    set_property(TARGET xdpctl PROPERTY C_EXTENSIONS ON)
    set_property(TARGET xskbench PROPERTY C_EXTENSIONS ON)
    target_include_directories(xdpctl PRIVATE ${CMAKE_SOURCE_DIR}/third_party/libbpf)
    target_include_directories(xskbench PRIVATE ${CMAKE_SOURCE_DIR}/third_party/libbpf)
    target_compile_options(xdpctl PRIVATE -Wno-pedantic)
    target_compile_options(xskbench PRIVATE -Wno-pedantic)
    target_link_libraries(xdpctl PRIVATE ${LIBBPF_LIBRARY})
    target_link_libraries(xskbench PRIVATE ${LIBBPF_LIBRARY})
    if(LIBELF_LIBRARY)
        target_link_libraries(xdpctl PRIVATE ${LIBELF_LIBRARY})
        target_link_libraries(xskbench PRIVATE ${LIBELF_LIBRARY})
    endif()
    if(LIBZ_LIBRARY)
        target_link_libraries(xdpctl PRIVATE ${LIBZ_LIBRARY})
        target_link_libraries(xskbench PRIVATE ${LIBZ_LIBRARY})
    endif()
    message(STATUS "XDP: clang=${CLANG_EXECUTABLE} libbpf=${LIBBPF_LIBRARY}")
else()
    message(WARNING "XDP skipped (need clang and libbpf). Userspace txgen/rxbench still build.")
endif()
