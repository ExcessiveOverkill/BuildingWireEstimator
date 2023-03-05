# BuildingWireEstimator

## Ignoring devices
If you would like certain outlet lables to be ignored, create a file called "ignoreDevices.txt" in the same directory as the input pdf
input the devices you want to ignore separated by commas, lables are case sensitive

## Adding Panels
You must add the names of the panels you want to find devices for to the "panels.txt" file
The names MUST match the names on the drawing, and the 2nd word(if 2 words ex: "PANEL "NH6A"") must be contained in each of the matching devices(the devices must contain "NH6A").
The panel names must be unique to only the panel, the word or word pair must not appear anywhere else on the document
The panel names cannot be more than 2 words.
They must be comma separated with no added spaces in the panels.txt file

## Running

Run the "main.exe" file to start the program

Answer the prompts and select the input pdf file

The program will save an image with wire runs overlayed and a .csv file with length information in the same directory as the input pdf


