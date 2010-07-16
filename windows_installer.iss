[Setup]
AppName =Jokosher
AppVerName=Jokosher version 0.11.5
DefaultDirName={pf}\Jokosher
DefaultGroupName=Jokosher
Compression=bzip/9

[InstallDelete]
Type: files; Name: {app}\*.dll
Type: files; Name: {app}\*.pyd

[Files]
Source: dist/*; DestDir: {app}; Flags: recursesubdirs createallsubdirs

[Icons]
Name: {group}\Jokosher; Filename: {app}\jokosher.exe; WorkingDir: {app}
Name: {group}\Uninstall Jokosher; Filename: {uninstallexe}
