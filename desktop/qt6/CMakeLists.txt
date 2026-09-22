cmake_minimum_required(VERSION 3.21)

project(IndiginousQt6Native
    VERSION 0.1.0
    LANGUAGES CXX
    DESCRIPTION "Native Qt 6 Widgets foundation for Indiginous"
)

include(CTest)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

option(INDIGINOUS_QT6_BUILD_APP "Build the Qt 6 Widgets application when Qt is available" ON)
option(INDIGINOUS_QT6_REQUIRE_TESTS "Fail configuration unless native interaction tests can be built" OFF)

set(INDIGINOUS_QT6_SOURCES
    src/main.cpp
    src/accessibility/accessibility_announcer.cpp
    src/app/main_window.cpp
    src/transport/protocol_client.cpp
    src/world/world_viewport.cpp
    src/input/command_router.cpp
)

set(INDIGINOUS_QT6_HEADERS
    src/app/main_window.h
    src/accessibility/accessibility_announcer.h
    src/transport/protocol_client.h
    src/world/world_viewport.h
    src/input/command_router.h
)

if(INDIGINOUS_QT6_BUILD_APP)
    find_package(Qt6 6.2 COMPONENTS Widgets Network WebSockets QUIET)
    if(Qt6Widgets_FOUND AND Qt6Network_FOUND AND Qt6WebSockets_FOUND)
        qt_add_executable(indiginous_qt6 ${INDIGINOUS_QT6_SOURCES} ${INDIGINOUS_QT6_HEADERS})
        target_include_directories(indiginous_qt6 PRIVATE src)
        target_link_libraries(indiginous_qt6 PRIVATE Qt6::Widgets Qt6::Network Qt6::WebSockets)
        target_compile_definitions(indiginous_qt6 PRIVATE
            INDIGINOUS_QT6_FOUND=1
            INDIGINOUS_QT6_FOUNDATION_VERSION="${PROJECT_VERSION}"
        )
        set_target_properties(indiginous_qt6 PROPERTIES
            WIN32_EXECUTABLE TRUE
            MACOSX_BUNDLE TRUE
        )
    else()
        message(WARNING
            "Qt 6 Widgets, Network, and WebSockets were not found; skipping "
            "indiginous_qt6. Install the complete Qt 6 desktop toolchain to build the native client.")
    endif()
endif()

if(BUILD_TESTING)
    find_package(Qt6 6.2 COMPONENTS Widgets Network WebSockets Test QUIET)
    if(Qt6Widgets_FOUND AND Qt6Network_FOUND AND Qt6WebSockets_FOUND AND Qt6Test_FOUND)
        qt_add_executable(indiginous_qt6_navigation_test
            tests/navigation_test.cpp
            src/input/command_router.cpp src/input/command_router.h
            src/world/world_viewport.cpp src/world/world_viewport.h
            src/transport/protocol_client.cpp src/transport/protocol_client.h)
        target_include_directories(indiginous_qt6_navigation_test PRIVATE src)
        target_link_libraries(indiginous_qt6_navigation_test PRIVATE Qt6::Widgets Qt6::Network Qt6::WebSockets Qt6::Test)
        add_test(NAME indiginous_qt6_navigation COMMAND indiginous_qt6_navigation_test)
        set_tests_properties(indiginous_qt6_navigation PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
    else()
        if(INDIGINOUS_QT6_REQUIRE_TESTS)
            message(FATAL_ERROR "Native interaction tests required, but Qt6 Widgets/Network/WebSockets/Test unavailable.")
        endif()
        message(WARNING "Qt navigation interaction tests NOT BUILT: Widgets/Network/WebSockets/Test required.")
    endif()
    find_package(Python3 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
        add_test(
            NAME indiginous_qt6_source_contract
            COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/source_contract.py
        )
    else()
        message(WARNING "Python 3 was not found; source-contract test is unavailable.")
    endif()
endif()

if(INDIGINOUS_QT6_REQUIRE_TESTS AND NOT BUILD_TESTING)
    message(FATAL_ERROR "INDIGINOUS_QT6_REQUIRE_TESTS requires BUILD_TESTING=ON.")
endif()
