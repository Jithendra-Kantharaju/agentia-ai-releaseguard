# Misses for method `baseline` (first 12)

## composer@composer:558512461  (category 0, 3783 lines)
Labelled failure lines:
  L1091: 1) Composer\Test\ApplicationTest::testDevWarning
  L1092: Function ReflectionType::__toString() is deprecated
  L1093: 
  L1094: /home/travis/build/composer/composer/tests/Composer/Test/ApplicationTest.php:25
  L1095: 
  L1096: 2) Composer\Test\ApplicationTest::testDevWarningPrevented
  L1097: Function ReflectionType::__toString() is deprecated
  L1098: 
Method cited:
  L3734: 3) Composer\Test\Util\BitbucketTest::testRequestAccessTokenWithValidOAuthConsumerAndExpiredAccessToken
  L3739: 4) Composer\Test\Util\BitbucketTest::testRequestAccessTokenWithUsernameAndPassword
  L3744: 5) Composer\Test\Util\BitbucketTest::testUsernamePasswordAuthenticationFlow
  L3749: 6) Composer\Test\Util\RemoteFilesystemTest::testGetOptionsForUrlWithStreamOptions
  L3750: ErrorException: Trying to access array offset on value of type null
  L3756: 7) Composer\Test\Util\RemoteFilesystemTest::testGetOptionsForUrlWithCallOptionsKeepsHeader
  L3757: ErrorException: Trying to access array offset on value of type null
  L3765: FAILED tests/Composer/Test/Util

## composer@composer:566904372  (category 1, 1341 lines)
Labelled failure lines:
  L1314:   Line   src/Composer/Installer.php                                    
  L1315:  ------ -------------------------------------------------------------- 
  L1316:   1174   Method Composer\Installer::updatePackageUrl() invoked with 8  
  L1317:          parameters, 7 required.                                       
Method cited:
  L225: Locale to use while parsing sudoers: C
  L1320:  [ERROR] Found 1 error                                                          

## discourse@discourse:565586706  (category 0, 4258 lines)
Labelled failure lines:
  L4176: app/assets/javascripts/discourse/routes/about.js.es6
Method cited:
  L225: Locale to use while parsing sudoers: C
  L4178: error Command failed with exit code 1.
  L4245: " exited with 1.

## dkhamsing@open-source-ios-apps:555180400  (category 0, 5886 lines)
Labelled failure lines:
  L5514: > Links 
  L5515:   1. [L0153] 404 http://a5.mzstatic.com/us/r30/Purple69/v4/b4/96/83/b49683ea-62bc-e9a5-9480-bd75e529d259/screen696x696.jpeg  
  L5516: > Dupes 
  L5517:   None ✓
Method cited:
  L225: Locale to use while parsing sudoers: C
  L4800:   1314. https://github.com/cpo007/S.C.P-Asylum-Fail 
  L4801:   1315. https://github.com/cpo007/S.C.P-Asylum-Fail/blob/master/Image/Launch.png 
  L4802:   1316. https://github.com/cpo007/S.C.P-Asylum-Fail/blob/master/Image/Home.png 

## dkhamsing@open-source-ios-apps:560605858  (category 0, 5893 lines)
Labelled failure lines:
  L5514: > Links 
  L5515:   1. [L0239] 522 http://www.wtfgamersonly.com/wp-content/uploads/2014/08/gba4ios.jpg  
  L5516:   2. [L1581] 404 https://github.com/mssun/passforios/raw/master/img/preview.gif  
  L5517: > Dupes 
  L5518:   None ✓
Method cited:
  L225: Locale to use while parsing sudoers: C
  L4801:   1315. https://github.com/cpo007/S.C.P-Asylum-Fail/blob/master/Image/Launch.png 
  L4802:   1316. https://github.com/cpo007/S.C.P-Asylum-Fail/blob/master/Image/Home.png 
  L5629:   01. [L0225]  https://douban.fm/ Failed to open TCP connection to douban.fm:443 (Connection timed out - connect(2) for "douban.fm" port 443) 

## electron@electron:303140404  (category 0, 1011 lines)
Labelled failure lines:
  L894: Error: Cannot find module './db.json'
  L895:     at Function.Module._resolveFilename (module.js:325:15)
  L896:     at Function.Module._load (module.js:276:25)
  L897:     at Module.require (module.js:353:17)
  L898:     at require (internal/module.js:12:17)
  L899:     at Object.<anonymous> (/home/travis/build/electron/electron/node_modules/request/node_modules/mime-types/node_modules/mime-db/index.js:11:18)
  L900:     at Module._compile (module.js:409:26)
  L901:     at Object.Module._extensions..js (module.js:416:10)
Method cited:
  L225: Locale to use while parsing sudoers: C
  L922: The command "eval npm install  " failed. Retrying, 2 of 3.
  L994: E: Failed to fetch http://dl.hhvm.com/ubuntu/dists/trusty/main/binary-i386/Packages  404  Not Found [IP: 52.84.14.226 80]
  L995: E: Some index files failed to download. They have been ignored, or old ones used instead.
  L997: Traceback (most recent call last):

## electron@electron:303144317  (category 0, 1014 lines)
Labelled failure lines:
  L900: Error: Cannot find module 'fast-deep-equal'
  L901:     at Function.Module._resolveFilename (module.js:325:15)
  L902:     at Function.Module._load (module.js:276:25)
  L903:     at Module.require (module.js:353:17)
  L904:     at require (internal/module.js:12:17)
  L905:     at Object.<anonymous> (/home/travis/build/electron/electron/node_modules/request/node_modules/har-validator/node_modules/ajv/lib/compile/resolve.js:4:13)
  L906:     at Module._compile (module.js:409:26)
  L907:     at Object.Module._extensions..js (module.js:416:10)
Method cited:
  L225: Locale to use while parsing sudoers: C
  L935: The command "eval npm install  " failed. Retrying, 2 of 3.
  L997: E: Failed to fetch http://dl.hhvm.com/ubuntu/dists/trusty/main/binary-i386/Packages  404  Not Found [IP: 13.33.164.241 80]
  L998: E: Some index files failed to download. They have been ignored, or old ones used instead.
  L1000: Traceback (most recent call last):

## elixir-lang@elixir:572202401  (category 1, 964 lines)
Labelled failure lines:
  L713: ** (CompileError) (for doctest at) lib/list.ex:102: undefined function i/1
  L714:     (elixir 1.10.0-dev) src/elixir_locals.erl:108: :elixir_locals."-ensure_no_undefined_local/3-lc$^0/1-0-"/2
  L715:     (elixir 1.10.0-dev) src/elixir_locals.erl:109: anonymous fn/3 in :elixir_locals.ensure_no_undefined_local/3
Method cited:
  L555: $ export ELIXIR_ASSERT_TIMEOUT=2000
  L712: == Compilation error in file test/elixir/list_test.exs ==
  L735:   'Elixir.Exception':message/1
  L736:   'Elixir.Exception':normalize/3

## elixir-lang@elixir:572202566  (category 1, 975 lines)
Labelled failure lines:
  L724: ** (CompileError) (for doctest at) lib/list.ex:102: undefined function i/1
  L725:     (elixir 1.10.0-dev) src/elixir_locals.erl:108: :elixir_locals."-ensure_no_undefined_local/3-lc$^0/1-0-"/2
  L726:     (elixir 1.10.0-dev) src/elixir_locals.erl:109: anonymous fn/3 in :elixir_locals.ensure_no_undefined_local/3
Method cited:
  L556: $ export ELIXIR_ASSERT_TIMEOUT=2000
  L723: == Compilation error in file test/elixir/list_test.exs ==
  L746:   'Elixir.Exception':message/1
  L747:   'Elixir.Exception':normalize/3

## emacs-tw@awesome-emacs:536981552  (category 0, 1609 lines)
Labelled failure lines:
  L1422: > Links 
  L1423:   1. [L296] 301 https://github.com/areina/helm-dash  → https://github.com/dash-docs-el/helm-dash 
  L1424:   2. [L494] 502 https://www.emacswiki.org/emacs/MakefileMode  
  L1425:   3. [L619] 502 https://www.emacswiki.org/emacs/CategoryEshell  
  L1426:   4. [L687] 301 https://github.com/dangxuandev/blog-admin  → https://github.com/xcodebuild/blog-admin 
  L1427:   5. [L771] 301 https://github.com/dunn/homebrew-emacs  → https://github.com/brew-stuff/homebrew-emacs 
  L1428: > Dupes 
  L1429:   None ✓
Method cited:
  L225: Locale to use while parsing sudoers: C

## emacs-tw@awesome-emacs:537024011  (category 0, 1586 lines)
Labelled failure lines:
  L1400: > Links 
  L1401:   1. [L296] 301 https://github.com/areina/helm-dash  → https://github.com/dash-docs-el/helm-dash 
  L1402:   2. [L687] 301 https://github.com/dangxuandev/blog-admin  → https://github.com/xcodebuild/blog-admin 
  L1403:   3. [L771] 301 https://github.com/dunn/homebrew-emacs  → https://github.com/brew-stuff/homebrew-emacs 
  L1404: > Dupes 
  L1405:   None ✓
Method cited:
  L225: Locale to use while parsing sudoers: C

## erlang@otp:546804521  (category 0, 1514 lines)
Labelled failure lines:
  L1122: (no logger present) unexpected logger message: {log,error,"Error in process ~p with exit value:~n~p~n",[<0.0.0>,{{badmatch,{error,{bad_lib,"Function not found prim_file:read_handle...
  L1123: 
  L1124: (no logger present) unexpected logger message: {log,error,"Error in process ~p with exit value:~n~p~n",[<0.0.0>,{{badmatch,{error,{bad_lib,"Function not found prim_file:read_handle...
  L1125: 
  L1126: (no logger present) unexpected logger message: {log,error,"Error in process ~p with exit value:~n~p~n",[<0.0.0>,{{badmatch,{error,{bad_lib,"Function not found prim_file:read_handle...
  L1127: 
  L1128: (no logger present) unexpected logger message: {log,error,"Error in process ~p with exit value:~n~p~n",[<0.0.0>,{{badmatch,{error,{bad_lib,"Function not found prim_file:read_handle...
  L1129: 
Method cited:
  L225: Locale to use while parsing sudoers: C
  L1121: Building OTP.................... failed.
  L1513: *** Failed ***

