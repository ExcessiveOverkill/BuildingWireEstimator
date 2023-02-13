import fitz, cv2
import numpy as np
import tkinter
from tkinter import filedialog
import time
import os.path
import csv

zoom = 2

def loadPDF(file_path):
    doc = fitz.open(file_path)

    wordsRaw = doc[0].get_textpage().extractWORDS()
    words = [list(ele) for ele in wordsRaw]
    blocksRaw = doc[0].get_textpage().extractBLOCKS()
    blocks = [list(ele) for ele in blocksRaw]
    pixelmap = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom))

    for item in range(len(words)):
        for value in range(4):
            words[item][value] = words[item][value] * zoom
    for item in range(len(blocks)):
        for value in range(4):
            blocks[item][value] = blocks[item][value] * zoom

    return words, blocks, pixelmap
    



def findPanelText(words, panelNames):
    #find panel text    #FIXME: add block based check for all found panels to verify they are panels and not devices
    panelText = []
    for wordData in words:
        word = wordData[4]
        if len(word) <= 3 or word[0:2] not in panelNames or word.count("-") != 1:
            continue
        panelText.append(wordData)
    return panelText


def findScale(pixelmap, blocks):
#find scale (pixels per foot)   #FIXME: use dimensions input from user of pdf sheet to generate scale
    scale = 0
    xPixelsPerInch = pixelmap.xres
    yPixelsPerInch = pixelmap.yres
    if xPixelsPerInch != yPixelsPerInch:
        raise Exception("Inconsistent x and y scales")
    for block in blocks:
        if "=" in block[4]:
            temp = block[4].split("\"")
            valA = int(temp[0].split("/")[0]) / int(temp[0].split("/")[1])
            valB = int(temp[1].replace("=", "").strip().split("'")[0]) + int(temp[1].split("-")[1].replace("\"", ""))/12
            scale = ((valB/valA)/(xPixelsPerInch * zoom))**-1
    return scale

def convertPdfToImage(pixelmap):
    pixelmap.save('tempImage.png')
    fullImage = cv2.imread('tempImage.png', cv2.IMREAD_GRAYSCALE)
    fullImage = cv2.flip(fullImage, 0)
    fullImage = cv2.rotate(fullImage, cv2.ROTATE_90_CLOCKWISE)
    fullImageColor = cv2.imread('tempImage.png', cv2.IMREAD_COLOR)
    fullImageColor = cv2.flip(fullImageColor, 0)
    fullImageColor = cv2.rotate(fullImageColor, cv2.ROTATE_90_CLOCKWISE)
    return fullImage, fullImageColor

def findExactPanelLocations(fullImage, panelText, textOnly=True):
    #find panel exact locations based on panel image
    exactPanelPoints = []

    for panel in panelText:
        searchSize = 2
        textWidth = panel[2] - panel[0]
        textHeight = panel[3] - panel[1]
        textCenterX = (panel[2] + panel[0]) / 2
        textCenterY = (panel[3] + panel[1]) / 2

        if textOnly:
            exactPanelPoints.append([panel[4], [int(textCenterY), int(textCenterX)]])
            continue

        smallerTextDimension = min(textWidth, textHeight)
        searchPadding = smallerTextDimension*searchSize
        searchImage = fullImage[int(panel[0]-searchPadding):int(panel[2]+searchPadding), int(panel[1]-searchPadding):int(panel[3]+searchPadding)]
        searchXsize, searchYsize = np.shape(searchImage)
        searchImage = cv2.GaussianBlur(searchImage,(7,7),0)

        ret, searchImage = cv2.threshold(searchImage,50,255,cv2.THRESH_BINARY)

        contours, hierarchy = cv2.findContours(searchImage, 1, cv2.CHAIN_APPROX_SIMPLE)

        bestContour = None
        bestDistance = 2000
        bestCenter = None
        minArea = 10 * zoom**2
        maxArea = 70 * zoom**2
        for cnt in contours:
            if cv2.contourArea(cnt) < minArea or cv2.contourArea(cnt) > maxArea:
                continue
            x,y,w,h = cv2.boundingRect(cnt)
            xDist = x+w/2 - searchXsize/2
            yDist = y+h/2 - searchYsize/2
            dist = np.sqrt(xDist**2 + yDist**2)
            if dist < bestDistance:
                bestDistance = dist
                bestContour = cnt
                bestCenter = [int(panel[1]-searchPadding + x+w/2), int(panel[0]-searchPadding + y+h/2)]

        if bestCenter is not None:
            exactPanelPoints.append([panel[4], bestCenter])

    return exactPanelPoints


def findExactOutletLocations(words, panelNames, ignoreNames, textOnly=True):
    # find exact RP "2" device location
    exactRP2Points = []
    for wordData in words:
        word = wordData[4]
        if len(word) <= 3 or word[0:2] not in panelNames or word.count("-") != 2 or word in ignoreNames:
            continue
        textCenterX = (wordData[2] + wordData[0]) / 2
        textCenterY = (wordData[3] + wordData[1]) / 2

        if textOnly:
            exactRP2Points.append([word, [int(textCenterY), int(textCenterX)], wordData])
            continue

        bestDistance = 10000
        for wordData2 in words:
            word2 = wordData2[4]
            if word2 != '2':
                continue
            textCenterX2 = (wordData2[2] + wordData2[0]) / 2
            textCenterY2 = (wordData2[3] + wordData2[1]) / 2
            xDist = textCenterX2 - textCenterX
            yDist = textCenterY2 - textCenterY
            dist = np.sqrt(xDist**2 + yDist**2)
            if dist < bestDistance:
                bestDistance = dist
                bestCenter = [int(textCenterY2), int(textCenterX2)]
        if bestDistance < 30*zoom:
            count = 0
            for foundPoint in exactRP2Points:
                count = foundPoint[0].count(word)
            if count > 0:
                word += f'_{count}'
            exactRP2Points.append([word, bestCenter, wordData])
    if textOnly:
        return exactRP2Points
    
    #correct for overlapping device locations
    for index1, device1 in enumerate(exactRP2Points):
        for index2, device2 in enumerate(exactRP2Points):
            if device1[0] == device2[0]:
                continue
            if np.array_equiv(device1[1], device2[1]):
                #print("duplicate found")

                dwordData1 = device1[2]
                dwordData2 = device2[2]

                textCenterX1 = (dwordData1[2] + dwordData1[0]) / 2
                textCenterY1 = (dwordData1[3] + dwordData1[1]) / 2
                textCenterX2 = (dwordData2[2] + dwordData2[0]) / 2
                textCenterY2 = (dwordData2[3] + dwordData2[1]) / 2

                bestDistance1 = 10000
                secondBestDistance1 = 10000
                bestDistance2 = 10000
                secondBestDistance2 = 10000
                for wordData2 in words:
                    word2 = wordData2[4]
                    
                    if word2 != '2':
                        continue

                    twoCenterX = (wordData2[2] + wordData2[0]) / 2
                    twoCenterY = (wordData2[3] + wordData2[1]) / 2

                    used = False
                    for point in exactRP2Points:
                        if point[1] == [twoCenterX, twoCenterY]:
                            used = True
                    if used: continue

                    xDist1 = twoCenterX - textCenterX1
                    yDist1 = twoCenterY - textCenterY1
                    xDist2 = twoCenterX - textCenterX2
                    yDist2 = twoCenterY - textCenterY2
                    dist1 = np.sqrt(xDist1**2 + yDist1**2)
                    dist2 = np.sqrt(xDist2**2 + yDist2**2)

                    secondBestCenterInUse1 = False
                    secondBestCenterInUse2 = False
                    
                    if dist1 < bestDistance1:
                        bestDistance1 = dist1
                        bestCenter1 = [int(twoCenterY), int(twoCenterX)]
                    if dist1 < secondBestDistance1 and dist1 > bestDistance1 and not secondBestCenterInUse1:
                        secondBestDistance1 = dist1
                        secondBestCenter1 = [int(twoCenterY), int(twoCenterX)]
                    
                    if dist2 < bestDistance2:
                        bestDistance2 = dist2
                        bestCenter2 = [int(twoCenterY), int(twoCenterX)]
                    if dist2 < secondBestDistance2 and dist2 > bestDistance2 and not secondBestCenterInUse2:
                        secondBestDistance2 = dist2
                        secondBestCenter2 = [int(twoCenterY), int(twoCenterX)]

                if secondBestDistance1 < secondBestDistance2:
                    exactRP2Points[index1][1] = secondBestCenter1
                    
                else:
                    exactRP2Points[index2][1] = secondBestCenter2
                    
    return exactRP2Points

def findScaledRectilinearDistances(exactPanelPoints, exactRP2Points, scale, fullImageColor=None):
    #find scaled rectilinear distances to devices in feet
    enableDrawing = False
    if fullImageColor is not None:
        enableDrawing = True
        textImage = np.zeros_like(fullImageColor)
        textImage = cv2.rotate(textImage, cv2.ROTATE_90_COUNTERCLOCKWISE)
    textOffset = [-10*zoom, 17*zoom]
    distances = []
    for panel in exactPanelPoints:
        if 'RP' in panel[0]:
            for device in exactRP2Points:
                if panel[0] in device[0]:
                    dist = abs(panel[1][0] - device[1][0]) + abs(panel[1][1] - device[1][1])
                    dist /= scale
                    distances.append([device[0], dist])
                    if enableDrawing:
                        fullImageColor = cv2.line(fullImageColor, panel[1], [device[1][0], panel[1][1]], [0, 0, 255], 2)
                        fullImageColor = cv2.line(fullImageColor, [device[1][0], panel[1][1]], device[1], [0, 0, 255], 2)
                        textImage = cv2.putText(textImage, f'{int(dist)}\'', [device[1][1] + textOffset[0], device[1][0] + textOffset[1]], fontFace=0, fontScale=.8, color=[0, 0, 255], thickness=2)
    if enableDrawing:
        return distances, textImage

    return distances, None

def drawOutletCircles(fullImageColor, exactRP2Points):
    for point in exactRP2Points:
        fullImageColor = cv2.circle(fullImageColor, point[1], 10*zoom, [0, 255, 0], 2)

def drawPanelCircles(fullImageColor, exactPanelPoints):
    for point in exactPanelPoints:
        fullImageColor = cv2.circle(fullImageColor, point[1], 10*zoom, [255, 0, 0], 2)

def saveOutputImage(fullImageColor, textImage, path):
    fullImageColor = cv2.rotate(fullImageColor, cv2.ROTATE_90_COUNTERCLOCKWISE)
    fullImageColor = cv2.flip(fullImageColor, 0)
    img2gray = cv2.cvtColor(textImage,cv2.COLOR_BGR2GRAY)
    ret,colorMask = cv2.threshold(img2gray,0,255,cv2.THRESH_BINARY)
    fullImageColor = cv2.bitwise_and(fullImageColor, fullImageColor, mask=cv2.bitwise_not(colorMask))
    fullImageColor = cv2.add(fullImageColor, textImage)
    cv2.imwrite(path, fullImageColor)

def getFirst(element):
    return element[0]

def getNumberKey(element):
    return int(element[0].split("-")[1])*100 + int(element[0].split("-")[2].split("_")[0])

def saveToCSV(path, RP2Points, PanelPoints, distances):
    panelTotals = [0] * len(PanelPoints)
    outputArray = [["Panel Names", "Total wire from panel", "Outlets", "Wire to outlet", "Total wire"]]
    PanelPoints.sort(key=getFirst)
    distances.sort(key=getNumberKey)
    for outlet in distances:
        outputArray.append([None, None, str(outlet[0]), str(outlet[1]), None])
        for index, panel in enumerate(PanelPoints):
            if outlet[0].count(panel[0]):
                panelTotals[index] += outlet[1]
    for index, panel in enumerate(PanelPoints):
        outputArray[index+1][0] = panel[0]
        outputArray[index+1][1] = str(panelTotals[index])

    outputArray[1][4] = np.sum(panelTotals)

    with open(path, "w") as csvFile:
        writer = csv.writer(csvFile, dialect="excel", lineterminator="\n")
        writer.writerows(outputArray)

def getYesNo(prompt, defaultAnswer=None):
    suffix = "(y/n)"
    if defaultAnswer is not None:
        if defaultAnswer == True:
            suffix = "(Y/n)"
        else:
            suffix = "(y/N)"
    while(True):
        response = input(prompt + suffix)
        if response.lower() == "y":
            return True
        elif response.lower() == "n":
            return False
        elif response == "" and defaultAnswer is not None:
            return defaultAnswer
        print("Not a valid input!")

def getNumber(prompt, defaultAnswer=None):
    while(True):
        response = input(prompt)
        if response == "" and defaultAnswer is not None:
            return  defaultAnswer
        try:
            number = float(response)
            return number
        except:
            print("Not a valid input!")



tkinter.Tk().withdraw() # prevents an empty tkinter window from appearing

useTextLocations = not getYesNo("Find precise object locations?", defaultAnswer=False)
scaleInput = getNumber("Scale adjust (leave blank to use found scale)", defaultAnswer=1)

file_path = filedialog.askopenfile(title="Select Input PDF").name

if file_path is None:
    print("No input file selected, program will exit")
    time.sleep(3)
    exit()

outputPath = os.path.dirname(file_path)
ignoreNames = ""
if os.path.exists(outputPath+"/ignoreDevices.txt") and getYesNo("Ignore file found, would you like to use it?", defaultAnswer=True):
    with open(outputPath+"/ignoreDevices.txt") as ignoreFile:
        data = ignoreFile.read().replace("\n", "").replace(" ", "")
        ignoreNames = data.split(",")
        print("Ignoring outlets: " + data.replace(",", ", "))
        
print("Loading PDF...", end="")
words, blocks, pixelmap = loadPDF(file_path)
print("Done")

print("Finding panels...", end="")
panelText = findPanelText(words, ["RP"])
print("Done")

print("Finding scale...", end="")
scaleInput = findScale(pixelmap, blocks) * scaleInput * (25/35)   #scale offset
print("Done")

print("Converting PDF to image...", end="")
fullImage, fullImageColor = convertPdfToImage(pixelmap)
print("Done")

print("Finding locations of panels...", end="")
exactPanelPoints = findExactPanelLocations(fullImage, panelText, textOnly=useTextLocations)
print("Done")

print("Finding locations of outlets...", end="")
exactRP2Points = findExactOutletLocations(words, ["RP"], ignoreNames, textOnly=useTextLocations)
print("Done")

print("Finding distances to outlets...", end="")
distances, textImage = findScaledRectilinearDistances(exactPanelPoints, exactRP2Points, scaleInput, fullImageColor)
print("Done")

print("Saving output image...", end="")
saveOutputImage(fullImageColor, textImage, path=outputPath+"/output.png")
print("Done")
print(f"Output image saved to {outputPath}/output.png")

print("Saving output CSV file...", end="")
saveToCSV(outputPath+"/output.csv", exactRP2Points, exactPanelPoints, distances)
print("Done")
print(f"Output CSV file saved to {outputPath}/output.csv")

print("Program finished, will now exit")
time.sleep(3)
exit()