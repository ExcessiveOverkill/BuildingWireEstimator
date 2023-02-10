import fitz, cv2
import numpy as np

### READ IN PDF
doc = fitz.open("sample.pdf")
zoom = 2

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
#pixelmap.set_dpi(20, 20)
#print(text)

#find panel text    #FIXME: add block based check for all found panels to verify they are panels and not devices
panelNames = ["DP", "RP"]
panelText = []
for wordData in words:
    word = wordData[4]
    if len(word) <= 3 or word[0:2] not in panelNames or word.count("-") != 1:
        continue
    panelText.append(wordData)

#find scale (pixels per foot)   #FIXME: use dimensions input from user of pdf sheet to generate scale
scale = 0
xPixelsPerInch = pixelmap.xres
yPixelsPerInch = pixelmap.yres
#print(xPixelsPerInch)
if xPixelsPerInch != yPixelsPerInch:
    raise Exception("Inconsistent x and y scales")
for block in blocks:
    if "=" in block[4]:
        temp = block[4].split("\"")
        valA = int(temp[0].split("/")[0]) / int(temp[0].split("/")[1])
        valB = int(temp[1].replace("=", "").strip().split("'")[0]) + int(temp[1].split("-")[1].replace("\"", ""))/12
        scale = ((valB/valA)/54)**-1
        #print(scale)

#find panel exact realworld locations
pixelmap.save('tempImage.png')
fullImage = cv2.imread('tempImage.png', cv2.IMREAD_GRAYSCALE)
fullImage = cv2.flip(fullImage, 0)
fullImage = cv2.rotate(fullImage, cv2.ROTATE_90_CLOCKWISE)
fullImageColor = cv2.imread('tempImage.png', cv2.IMREAD_COLOR)
fullImageColor = cv2.flip(fullImageColor, 0)
fullImageColor = cv2.rotate(fullImageColor, cv2.ROTATE_90_CLOCKWISE)
exactPanelPoints = []

for panel in panelText:
    searchSize = 2
    textWidth = panel[2] - panel[0]
    textHeight = panel[3] - panel[1]
    textCenterX = (panel[2] + panel[0]) / 2
    textCenterY = (panel[3] + panel[1]) / 2
    smallerTextDimension = min(textWidth, textHeight)
    searchPadding = smallerTextDimension*searchSize
    searchImage = fullImage[int(panel[0]-searchPadding):int(panel[2]+searchPadding), int(panel[1]-searchPadding):int(panel[3]+searchPadding)]
    searchXsize, searchYsize = np.shape(searchImage)
    searchImage = cv2.GaussianBlur(searchImage,(7,7),0)

    ret,searchImage = cv2.threshold(searchImage,50,255,cv2.THRESH_BINARY)

    contours,hierarchy = cv2.findContours(searchImage, 1, cv2.CHAIN_APPROX_SIMPLE)

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
    #x,y,w,h = cv2.boundingRect(bestContour)
    #cv2.rectangle(searchImage,(x,y),(x+w,y+h),128,1)
    #cv2.imshow('Panel Search Zone', searchImage)
    #cv2.waitKey(0)
    #break

ignoreNames = ""
#ignoreNames = "RP-78-12, RP-76-12, RP-87-8, RP-85-16, RP-85-8, RP-85-3, RP-85-4, RP-85-1, RP-85-2, RP-74-1, RP-74-2, RP-74-3, RP-74-4, RP-76-2, RP-76-12, RP-77-13, RP-75-1"
# find exact RP "2" device location
exactRP2Points = []
#print(words)
for wordData in words:
    word = wordData[4]
    if len(word) <= 3 or word[0:2] not in panelNames or word.count("-") != 2 or word in ignoreNames:
        continue
    textCenterX = (wordData[2] + wordData[0]) / 2
    textCenterY = (wordData[3] + wordData[1]) / 2

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
        #print(bestDistance)
        count = 0
        for foundPoint in exactRP2Points:
            #print(f'{foundPoint[0]} and {word}')
            count = foundPoint[0].count(word)
        if count > 0:
            word += f'_{count}'
        exactRP2Points.append([word, bestCenter, wordData])

#print(exactRP2Points)
duplicatePoints = []
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
                # try:
                #     for point in exactRP2Points:
                #         if point[1] == secondBestCenter1:
                #             secondBestCenterInUse1 = True
                #         if point[1] == secondBestCenter2:
                #             secondBestCenterInUse2 = True
                # except:
                #     pass
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

            #if  not np.array_equiv(bestCenter1, bestCenter2):
            #    raise Exception('Did not find match for items flagged as duplicates')
            #fullImage = cv2.circle(fullImage, bestCenter1, 25, 50, 3)
            #fullImage = cv2.circle(fullImage, secondBestCenter1, 10, 0, 3)
            #fullImage = cv2.circle(fullImage, secondBestCenter2, 15, 0, 3)
            # secondBestCenterInUse1 = False
            # secondBestCenterInUse2 = False
            # for point in exactRP2Points:
            #     if point[1] == secondBestCenter1:
            #         secondBestCenterInUse1 = True
            #     if point[1] == secondBestCenter2:
            #         secondBestCenterInUse2 = True
            # try:
            #     raise 
            #     fullImage = cv2.circle(fullImage, secondBestCenter1, 10, 0, 3)
            #     fullImage = cv2.circle(fullImage, secondBestCenter2, 15, 0, 3)
            #     if secondBestCenterInUse2 == 0 and secondBestCenterInUse1 == 0:
            #         raise Exception('second best choises are both aready taken! cannot find alternate match')
            #     elif secondBestCenterInUse2 == 1 and secondBestCenterInUse1 == 1:
            #         raise Exception('second best choises are both available, cannot determine correct assignment to fix duplicate lables')

            #     if not secondBestCenterInUse1:
            #         exactRP2Points[index1][1] = secondBestCenter1

            #     if not secondBestCenterInUse2:
            #         exactRP2Points[index2][1] = secondBestCenter2
            # except:
            #     pass
            if secondBestDistance1 < secondBestDistance2:
                exactRP2Points[index1][1] = secondBestCenter1
                #fullImage = cv2.circle(fullImage, secondBestCenter1, 10, 0, 2)
            else:
                exactRP2Points[index2][1] = secondBestCenter2
                #fullImage = cv2.circle(fullImage, secondBestCenter2, 10, 0, 2)



#find scaled rectilinear distances to devices in feet
textImage = np.zeros_like(fullImageColor)
textImage = cv2.rotate(textImage, cv2.ROTATE_90_COUNTERCLOCKWISE)
distances = []
for panel in exactPanelPoints:
    if 'RP' in panel[0]:
        for device in exactRP2Points:
            if panel[0] in device[0]:
                fullImageColor = cv2.line(fullImageColor, panel[1], [device[1][0], panel[1][1]], [0, 0, 255], 2)
                fullImageColor = cv2.line(fullImageColor, [device[1][0], panel[1][1]], device[1], [0, 0, 255], 2)
                #fullImage = cv2.circle(fullImage, point[1], 20, 0, 3)
                dist = abs(panel[1][0] - device[1][0]) + abs(panel[1][1] - device[1][1])
                dist /= scale
                distances.append([device[0], dist])
                #textImage = cv2.putText(textImage, f'{int(dist)}\'', device[1], fontFace=0, fontScale=.5, color=[255, 0, 0], thickness=1)
                textOffset = [-20, 35]
                textImage = cv2.putText(textImage, f'{int(dist)}\'', [device[1][1] + textOffset[0], device[1][0] + textOffset[1]], fontFace=0, fontScale=.8, color=[0, 0, 255], thickness=2)
#print(distances)

for point in exactRP2Points:
    fullImageColor = cv2.circle(fullImageColor, point[1], 10*zoom, [0, 255, 0], 2)

for point in exactPanelPoints:
    fullImageColor = cv2.circle(fullImageColor, point[1], 10*zoom, [255, 0, 0], 2)

fullImageColor = cv2.rotate(fullImageColor, cv2.ROTATE_90_COUNTERCLOCKWISE)
fullImageColor = cv2.flip(fullImageColor, 0)
img2gray = cv2.cvtColor(textImage,cv2.COLOR_BGR2GRAY)
ret,colorMask = cv2.threshold(img2gray,0,255,cv2.THRESH_BINARY)
fullImageColor = cv2.bitwise_and(fullImageColor, fullImageColor, mask=cv2.bitwise_not(colorMask))
fullImageColor = cv2.add(fullImageColor, textImage)
cv2.imwrite('output.png', fullImageColor)
#fullImage = cv2.resize(fullImage, [1920, 1080])
#cv2.imshow('Panels', fullImage)
#cv2.waitKey(0)
# for page in doc:
#     ### SEARCH
#     text = "RP-76"
#     text_instances = page.search_for(text)

#     ### HIGHLIGHT
#     for inst in text_instances:
#         highlight = page.add_highlight_annot(inst)
#         highlight.update()

# ### OUTPUT
# doc.save("output.pdf", garbage=4, deflate=True, clean=True)

