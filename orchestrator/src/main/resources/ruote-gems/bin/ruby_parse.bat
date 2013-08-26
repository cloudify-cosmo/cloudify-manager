@ECHO OFF
IF NOT "%~f0" == "~f0" GOTO :WinNT
@"jruby-complete-1.7.3.jar" "D:/dev/ruote/ruote-java/gems/ruote-gems/bin/ruby_parse" %1 %2 %3 %4 %5 %6 %7 %8 %9
GOTO :EOF
:WinNT
@"jruby-complete-1.7.3.jar" "%~dpn0" %*
