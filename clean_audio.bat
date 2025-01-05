@echo off
set inputDir=.\MXK
set outputDir=.\cleanedMXK

:: Create the output directory if it doesn't exist
if not exist "%outputDir%" mkdir "%outputDir%"

:: Loop through all .wav files in the input directory
for %%f in ("%inputDir%\*.wav") do (
    if not exist "%outputDir%\%%~nxf" (
        echo Processing "%%~nxf"...
        ffmpeg -i "%%f" -af "silenceremove=start_periods=1:start_duration=0.5:start_threshold=-40dB:stop_periods=-1:stop_duration=0.5:stop_threshold=-40dB,aresample=48000,apad=pad_dur=0.02" "%outputDir%\%%~nxf"
    ) else (
        echo Skipping "%%~nxf" - already processed.
    )
)

echo All files processed.
pause
