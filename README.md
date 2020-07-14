Better Editor (QGIS plugin)
===
![Icon](./icon.png)

This plugin improves the embedded Python editor with several useful features.

- Smart autocompletion and call tips with Jedi


- Replace comment / uncomment action with a single well-behaved Toggle comment action (`Ctrl+:`)

![toggleComment](./docs/toggle.gif)
- Format code with [black formatter](https://github.com/psf/black) (`Ctrl+Alt+F` or Format on save)

![formatCode](./docs/black.gif)
- Insert icon from QGIS resources: useful for quick prototyping
- Tweak some QGIS shortcuts which prevented user from entering `}` and `|` in the console when keyboard used AZERTY (French) layout
- Pressing Ctrl+S and Ctrl+Shift+S triggers file save when editor has focus
- Pressing Ctrl+R triggers script run
- Tab navigation with `Ctrl+PgDown` and `Ctrl+PgUp`
- Multiple syntax error check with [jedi](https://github.com/davidhalter/jedi).

![syntax check](./docs/syntax_check.png)
<sup><i>Original, simple check (QGIS) and multi check (Jedi)</i></sup>

Settings dialog
---

 ![Settings dialog](./docs/settings_dialog.png)
 - Hide default QGIS comment & uncomment actions
 - Set the max line length (will be used by the ruler, and black)
 - Format on save applies black before saving file
 - Configure the ruler
 - Change the default folding indicator (QGIS default is `Plain`)



Resource browser
---
![Resource browser](./docs/resource_browser.png)


The resource browser allow to search through the embedded .qrc files to look for images to use as icon.


*Copyright © 2020 Yoann Quenach de Quivillic*

