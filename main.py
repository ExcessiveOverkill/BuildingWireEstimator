import fitz, cv2
import numpy as np

### READ IN PDF
doc = fitz.open("sample.pdf")

words = doc[0].get_textpage().extractWORDS()
blocks = doc[0].get_textpage().extractBLOCKS()
pixelmap = doc[0].get_pixmap()
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
    searchImage = cv2.GaussianBlur(searchImage,(3,3),0)

    ret,searchImage = cv2.threshold(searchImage,50,255,cv2.THRESH_BINARY)

    contours,hierarchy = cv2.findContours(searchImage, 1, cv2.CHAIN_APPROX_SIMPLE)

    bestContour = None
    bestDistance = 2000
    bestCenter = None
    minArea = 10
    maxArea = 70
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
    
# find exact RP "2" device location
exactRP2Points = []
#print(words)
for wordData in words:
    word = wordData[4]
    if len(word) <= 3 or word[0:2] not in panelNames or word.count("-") != 2:
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
    if bestDistance < 30:
        #print(bestDistance)
        exactRP2Points.append([word, bestCenter])

duplicatePoints = []
#correct for overlapping device locations
for device1 in exactRP2Points:
    for device2 in exactRP2Points:
        if device1[0] == device2[0]:
            continue
        if np.array_equiv(device1[1], device2[1]):
            print("duplicate found")

            dwordData1 = []
            dwordData2 = []

            for wordData in words:
                word = wordData[4]
                if word == device1[0]:
                    dwordData1 = wordData
                    print(wordData)
                elif word == device2[0]:
                    dwordData2 = wordData
                    print(wordData)
                else: 
                    continue
        
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
                xDist1 = twoCenterX - textCenterX1
                yDist1 = twoCenterY - textCenterY1
                xDist2 = twoCenterX - textCenterX2
                yDist2 = twoCenterY - textCenterY2
                dist1 = np.sqrt(xDist1**2 + yDist1**2)
                dist2 = np.sqrt(xDist2**2 + yDist2**2)
                if dist1 < bestDistance1:
                    bestDistance1 = dist1
                    bestCenter1 = [int(twoCenterY), int(twoCenterX)]
                if dist1 < secondBestDistance1 and dist1 > bestDistance1:
                    secondBestDistance1 = dist1
                    secondBestCenter1 = [int(twoCenterY), int(twoCenterX)]
                
                if dist2 < bestDistance2:
                    bestDistance2 = dist2
                    bestCenter2 = [int(twoCenterY), int(twoCenterX)]
                if dist2 < secondBestDistance2 and dist2 > bestDistance2:
                    secondBestDistance2 = dist2
                    secondBestCenter2 = [int(twoCenterY), int(twoCenterX)]

            if  not np.array_equiv(bestCenter1, bestCenter2):
                raise Exception('Did not find match for items flagged as duplicates')


#find scaled rectilinear distances to devices in feet
distances = []
for panel in exactPanelPoints:
    if 'RP' in panel[0]:
        for device in exactRP2Points:
            if panel[0] in device[0]:
                dist = abs(panel[1][0] - device[1][0]) + abs(panel[1][1] - device[1][1])
                dist /= scale
                distances.append([device[0], dist])
#print(distances)

for point in duplicatePoints:
    fullImage = cv2.circle(fullImage, point[1], 20, 0, 3)

for point in exactPanelPoints:
    fullImage = cv2.circle(fullImage, point[1], 20, 128, 3)

fullImage = cv2.rotate(fullImage, cv2.ROTATE_90_COUNTERCLOCKWISE)
fullImage = cv2.flip(fullImage, 0)
cv2.imwrite('output.png', fullImage)
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

