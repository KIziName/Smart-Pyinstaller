## Smart-PyInstaller
· A simple GUI helper for building Python projects with PyInstaller.

## Features:
· Automatic discovery of .py scripts in the project folder (main.py is placed first in the list).

· AST analysis of source code
and automatic detection of used libraries.

· Build into a single file (--onefile) with a configurable name.

· Apply an icon (Windows only, .ico).

## Build options:
· Show/hide the console window (--noconsole);

· Request administrator privileges (--uac-admin, Windows);

· Clean cache before build (--clean);

· Keep .spec and/or the build/ folder.

· Live log with color highlighting, progress bar, and a button to open dist/.

· Cross-platform: Windows, Linux.

· Properly terminates the PyInstaller child process when the window is closed.

## Requirements:
***Python 3.8+***

· `pip install pyinstaller`

## How to use:
· Specify the project folder (default — current directory). The “Rescan” button rescans the project.

· Entry script & EXE/ELF name — select the entry point and set the output file name.

· App icon — if needed, select a .ico file (available only on Windows).

· Build options — check the libraries to bundle and the build parameters.

· Click ▶ Build and watch the log.

· The finished file will appear in dist/. The 📂 Open dist/ button opens the folder.

## Notes:
· On Linux, the --noconsole flag is ignored, and --uac-admin is skipped — a corresponding warning will appear in the log.

· Icon formats other than .ico are not supported on Windows.


## Smart-PyInstaller
- Простой графический помощник для сборки Python-проектов через PyInstaller.

## Возможности:
- Автоматический поиск .py-скриптов в папке проекта (файл main.py ставится первым в списке).
- AST-анализ исходников и автоопределение используемых библиотек.
- Сборка в один файл (--onefile) с настраиваемым именем.
- Применение иконки (только Windows, .ico).

## Опции сборки:
- Показать/скрыть консольное окно (--noconsole);
- Запросить права администратора (--uac-admin, Windows);
- Очистка кэша перед сборкой (--clean);
- Сохранить .spec и/или папку build/.
- Живой лог с цветовой подсветкой, прогресс-бар, кнопка открытия dist/.
- Кросс-платформенность: Windows, Linux.
- Корректное завершение дочернего процесса PyInstaller при закрытии окна.

## Требования:
***Python 3.8+***
- `pip install pyinstaller`

## Как пользоваться:
- Укажите папку с проектом (по умолчанию — текущая директория). Кнопка «Rescan» пересканирует проект.
- Entry script & EXE/ELF name — выберите точку входа и задайте имя итогового файла.
- App icon — при необходимости выберите .ico (доступно только на Windows).
- Build options — отметьте библиотеки для бандла и параметры сборки.
- Нажмите ▶ Build и следите за логом.
- Готовый файл появится в dist/. Кнопка 📂 Open dist/ откроет папку.

## Примечания:
- На Linux флаг --noconsole игнорируется, а --uac-admin пропускается — в логе будет соответствующее предупреждение.
- Форматы иконок кроме .ico на Windows не поддерживаются.
