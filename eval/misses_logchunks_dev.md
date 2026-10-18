# Misses for method `baseline` (first 12)

## BVLC@caffe:214074807  (category 0)
Labelled failure lines:
  L3974: CMake Error at /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:138 (message):
  L3975:   Could NOT find Halide (missing: HALIDE_ROOT_DIR HALIDE_LIBRARIES
  L3976:   HALIDE_INCLUDE_DIR)
  L3977: Call Stack (most recent call first):
  L3978:   /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:374 (_FPHSA_FAILURE_MESSAGE)
  L3979:   cmake/Modules/FindHalide.cmake:38 (find_package_handle_standard_args)
  L3980:   cmake/Dependencies.cmake:209 (find_package)
  L3981:   CMakeLists.txt:46 (include)
Method cited:
  (nothing)

## BVLC@caffe:214077363  (category 0)
Labelled failure lines:
  L3981: CMake Error at /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:138 (message):
  L3982:   Could NOT find Halide (missing: HALIDE_ROOT_DIR HALIDE_LIBRARIES
  L3983:   HALIDE_INCLUDE_DIR)
  L3984: Call Stack (most recent call first):
  L3985:   /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:374 (_FPHSA_FAILURE_MESSAGE)
  L3986:   cmake/Modules/FindHalide.cmake:38 (find_package_handle_standard_args)
  L3987:   cmake/Dependencies.cmake:209 (find_package)
  L3988:   CMakeLists.txt:46 (include)
Method cited:
  (nothing)

## BVLC@caffe:214247336  (category 0)
Labelled failure lines:
  L3974: CMake Error at /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:138 (message):
  L3975:   Could NOT find Halide (missing: HALIDE_LIBRARIES HALIDE_INCLUDE_DIR)
  L3976: Call Stack (most recent call first):
  L3977:   /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:374 (_FPHSA_FAILURE_MESSAGE)
  L3978:   cmake/Modules/FindHalide.cmake:38 (find_package_handle_standard_args)
  L3979:   cmake/Dependencies.cmake:209 (find_package)
  L3980:   CMakeLists.txt:46 (include)
Method cited:
  (nothing)

## BVLC@caffe:214320399  (category 1)
Labelled failure lines:
  L3941: ./scripts/travis/install-deps.sh: line 117: cd: ./scripts/travis: No such file or directory
Method cited:
  (nothing)

## BVLC@caffe:214320609  (category 1)
Labelled failure lines:
  L3914: ./scripts/travis/install-deps.sh: line 117: cd: ./scripts/travis: No such file or directory
Method cited:
  (nothing)

## BVLC@caffe:214327990  (category 0)
Labelled failure lines:
  L4003: CMake Error at /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:138 (message):
  L4004:   Could NOT find Halide (missing: HALIDE_LIBRARIES HALIDE_INCLUDE_DIR)
  L4005: Call Stack (most recent call first):
  L4006:   /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:374 (_FPHSA_FAILURE_MESSAGE)
  L4007:   cmake/Modules/FindHalide.cmake:38 (find_package_handle_standard_args)
  L4008:   cmake/Dependencies.cmake:209 (find_package)
  L4009:   CMakeLists.txt:46 (include)
Method cited:
  (nothing)

## BVLC@caffe:214329485  (category 0)
Labelled failure lines:
  L3937: CMake Error at /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:138 (message):
  L3938:   Could NOT find Halide (missing: HALIDE_LIBRARIES HALIDE_INCLUDE_DIR)
  L3939: Call Stack (most recent call first):
  L3940:   /usr/share/cmake-3.2/Modules/FindPackageHandleStandardArgs.cmake:374 (_FPHSA_FAILURE_MESSAGE)
  L3941:   cmake/Modules/FindHalide.cmake:38 (find_package_handle_standard_args)
  L3942:   cmake/Dependencies.cmake:209 (find_package)
  L3943:   CMakeLists.txt:46 (include)
Method cited:
  (nothing)

## BVLC@caffe:221812641  (category 2)
Labelled failure lines:
  L3758: CMake Error at /usr/share/cmake-3.2/Modules/FindBoost.cmake:1201 (message):
  L3759:   Unable to find the requested Boost libraries.
  L3760: 
  L3761:   Boost version: 1.54.0
  L3762: 
  L3763:   Boost include path: /usr/include
  L3764: 
  L3765:   Detected version of Boost is too old.  Requested version was 1.55 (or
Method cited:
  (nothing)

## BurntSushi@ripgrep:524197508  (category 0)
Labelled failure lines:
  L957: configure: error: in `/home/travis/build/BurntSushi/ripgrep/target/i686-unknown-linux-musl/debug/build/jemalloc-sys-754a2cc36ac04a65/out/build':
  L958: configure: error: C compiler cannot create executables
  L959: See `config.log' for more details
  L960: thread 'main' panicked at 'command did not execute successfully: "sh" "/home/travis/build/BurntSushi/ripgrep/target/i686-unknown-linux-musl/debug/build/jemalloc-sys-754a2cc36ac04a6...
  L961: expected success, got: exit code: 77', /home/travis/.cargo/registry/src/github.com-1ecc6299db9ec823/jemalloc-sys-0.3.0/build.rs:370:9
  L962: stack backtrace:
  L963:    0:     0x5597a5c1a753 - std::sys::unix::backtrace::tracing::imp::unwind_backtrace::h6bfa65e4a0f076ef
  L964:                                at src/libstd/sys/unix/backtrace/tracing/gcc_s.rs:39
Method cited:
  L921: error: failed to run custom build command for `jemalloc-sys v0.3.0`
  L1000: warning: build failed, waiting for other jobs to finish...
  L1001: error: build failed
  L1003: The command "ci/script.sh" exited with 101.
  L1007: Done. Your build exited with 1.

## BurntSushi@ripgrep:524343295  (category 0)
Labelled failure lines:
  L956: configure: error: in `/home/travis/build/BurntSushi/ripgrep/target/i686-unknown-linux-musl/debug/build/jemalloc-sys-8599e81d749c60c3/out/build':
  L957: configure: error: C compiler cannot create executables
  L958: See `config.log' for more details
  L959: thread 'main' panicked at 'command did not execute successfully: "sh" "/home/travis/build/BurntSushi/ripgrep/target/i686-unknown-linux-musl/debug/build/jemalloc-sys-8599e81d749c60c...
  L960: expected success, got: exit code: 77', /home/travis/.cargo/registry/src/github.com-1ecc6299db9ec823/jemalloc-sys-0.3.0/build.rs:370:9
  L961: stack backtrace:
  L962:    0:     0x55ffe43f9ad3 - std::sys::unix::backtrace::tracing::imp::unwind_backtrace::h805294fd9a8a1853
  L963:                                at src/libstd/sys/unix/backtrace/tracing/gcc_s.rs:39
Method cited:
  L920: error: failed to run custom build command for `jemalloc-sys v0.3.0`
  L999: warning: build failed, waiting for other jobs to finish...
  L1000: error: build failed
  L1002: The command "ci/script.sh" exited with 101.
  L1006: Done. Your build exited with 1.

## BurntSushi@ripgrep:524430085  (category 0)
Labelled failure lines:
  L1618: thread 'main' panicked at 'called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }', src/libcore/result.rs:999:5
  L1619: note: Run with `RUST_BACKTRACE=1` environment variable to display a backtrace.
Method cited:
  L1612: error: failed to run custom build command for `pcre2-sys v0.2.0`
  L1621: warning: build failed, waiting for other jobs to finish...
  L1623: error: build failed
  L1625: The command "ci/script.sh" exited with 101.
  L1629: Done. Your build exited with 1.

## BurntSushi@ripgrep:524433448  (category 0)
Labelled failure lines:
  L1637: thread 'main' panicked at 'called `Result::unwrap()` on an `Err` value: Os { code: 2, kind: NotFound, message: "No such file or directory" }', src/libcore/result.rs:999:5
  L1638: note: Run with `RUST_BACKTRACE=1` environment variable to display a backtrace.
Method cited:
  L1631: error: failed to run custom build command for `pcre2-sys v0.2.0`
  L1640: warning: build failed, waiting for other jobs to finish...
  L1642: error: build failed
  L1644: The command "ci/script.sh" exited with 101.
  L1648: Done. Your build exited with 1.

