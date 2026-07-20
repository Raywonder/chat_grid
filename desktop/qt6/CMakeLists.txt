cmake_minimum_required(VERSION 3.21)

project(EndiginousQt6Native
    VERSION 0.1.0
    LANGUAGES CXX
    DESCRIPTION "Native Qt 6 Widgets foundation for Endiginous"
)

include(CTest)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_AUTOMOC ON)

option(CHATGRID_QT6_BUILD_APP "Build the Qt 6 Widgets application when Qt is available" ON)

set(CHATGRID_QT6_SOURCES
    src/main.cpp
    src/app/main_window.cpp
    src/transport/protocol_client.cpp
    src/world/world_viewport.cpp
)

set(CHATGRID_QT6_HEADERS
    src/app/main_window.h
    src/transport/protocol_client.h
    src/world/world_viewport.h
)

if(CHATGRID_QT6_BUILD_APP)
    find_package(Qt6 6.2 COMPONENTS Widgets QUIET)
    if(Qt6Widgets_FOUND)
        qt_add_executable(chat_grid_qt6 ${CHATGRID_QT6_SOURCES} ${CHATGRID_QT6_HEADERS})
        target_include_directories(chat_grid_qt6 PRIVATE src)
        target_link_libraries(chat_grid_qt6 PRIVATE Qt6::Widgets)
        target_compile_definitions(chat_grid_qt6 PRIVATE
            CHATGRID_QT6_FOUND=1
            CHATGRID_QT6_FOUNDATION_VERSION="${PROJECT_VERSION}"
        )
        set_target_properties(chat_grid_qt6 PROPERTIES
            WIN32_EXECUTABLE TRUE
            MACOSX_BUNDLE TRUE
        )
    else()
        message(WARNING
            "Qt 6 Widgets was not found; skipping chat_grid_qt6. "
            "Install Qt 6 with the Widgets module to build the native client.")
    endif()
endif()

if(BUILD_TESTING)
    find_package(Python3 COMPONENTS Interpreter QUIET)
    if(Python3_Interpreter_FOUND)
        add_test(
            NAME chat_grid_qt6_source_contract
            COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/source_contract.py
        )
    else()
        message(WARNING "Python 3 was not found; source-contract test is unavailable.")
    endif()
endif()
