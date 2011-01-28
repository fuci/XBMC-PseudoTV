import xbmc, xbmcgui, xbmcaddon
import subprocess, os
import time, threading
import datetime

from Playlist import Playlist
from Globals import *
from Channel import Channel



class EPGWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.focusRow = 0
        self.focusIndex = 0
        self.focusTime = 0
        self.focusEndTime = 0
        self.shownTime = 0
        self.centerChannel = 0
        self.rowCount = 5
        self.channelButtons = [None] * 5
        self.actionSemaphore = threading.BoundedSemaphore()

        for i in range(5):
            self.channelButtons[i] = []


    def onFocus(self, controlid):
        pass


    # set the time labels
    def setTimeLabels(self, thetime):
        self.log('setTimeLabels')
        now = datetime.datetime.fromtimestamp(thetime)
        self.getControl(104).setLabel(now.strftime('%A, %b %d'))
        delta = datetime.timedelta(minutes=30)

        for i in range(3):
            self.getControl(101 + i).setLabel(now.strftime("%I:%M"))
            now = now + delta

        self.log('setTimeLabels return')


    def log(self, msg):
        log('EPG: ' + msg)


    def onInit(self):
        self.log('onInit')

        if self.setChannelButtons(time.time(), self.MyOverlayWindow.currentChannel) == False:
            self.log('Unable to add channel buttons')
            return

        curtime = time.time()
        self.focusIndex = 0
        basex, basey = self.getControl(113).getPosition()
        baseh = self.getControl(113).getHeight()
        basew = self.getControl(113).getWidth()

        # set the button that corresponds to the currently playing show
        for i in range(len(self.channelButtons[2])):
            left, top = self.channelButtons[2][i].getPosition()
            width = self.channelButtons[2][i].getWidth()
            left = left - basex
            starttime = self.shownTime + (left / (basew / 5400.0))
            endtime = starttime + (width / (basew / 5400.0))

            if curtime >= starttime and curtime <= endtime:
                self.focusIndex = i
                self.setFocus(self.channelButtons[2][i])
                self.focusTime = starttime + 30
                self.focusEndTime = endtime
                break

        self.focusRow = 2
        self.setShowInfo()
        self.log('onInit return')


    # setup all channel buttons for a given time
    def setChannelButtons(self, starttime, curchannel):
        self.log('setChannelButtons ' + str(starttime) + ', ' + str(curchannel))
        self.centerChannel = self.MyOverlayWindow.fixChannel(curchannel)
        curchannel = self.MyOverlayWindow.fixChannel(curchannel - 2)
        starttime = int(starttime)
        starttime = self.roundToHalfHour(starttime)
        self.setTimeLabels(starttime)
        self.shownTime = starttime
        tmpx, bary = self.getControl(120).getPosition()
        basex, basey = self.getControl(111).getPosition()
        basew = self.getControl(111).getWidth()

        for i in range(self.rowCount):
            self.setButtons(starttime, curchannel, i)
            self.getControl(301 + i).setLabel(self.MyOverlayWindow.channels[curchannel - 1].name)
            
            try:
                self.getControl(311 + i).setLabel(str(curchannel))
            except:
                pass

            try:
                self.getControl(321 + i).setImage(IMAGES_LOC + "Channel_" + str(curchannel) + ".png")
            except:
                pass

            curchannel = self.MyOverlayWindow.fixChannel(curchannel + 1)

        if time.time() >= starttime and time.time() < starttime + 5400:
            dif = int((starttime + 5400 - time.time()))
            self.getControl(120).setPosition((basex + basew - 2) - (dif * (basew / 5400.0)), bary)
        else:
            if time.time() < starttime:
                self.getControl(120).setPosition(basex + 2, bary)
            else:
                self.getControl(120).setPosition(basex + basew - 2, bary)

        self.log('setChannelButtons return')


    # round the given time down to the nearest half hour
    def roundToHalfHour(self, thetime):
        n = datetime.datetime.fromtimestamp(thetime)
        delta = datetime.timedelta(minutes=30)

        if n.minute > 29:
            n = n.replace(minute=30, second=0, microsecond=0)
        else:
            n = n.replace(minute=0, second=0, microsecond=0)

        return time.mktime(n.timetuple())


    # create the buttons for the specified channel in the given row
    def setButtons(self, starttime, curchannel, row):
        self.log('setButtons ' + str(starttime) + ", " + str(curchannel) + ", " + str(row))
        curchannel = self.MyOverlayWindow.fixChannel(curchannel)
        basex, basey = self.getControl(111 + row).getPosition()
        baseh = self.getControl(111 + row).getHeight()
        basew = self.getControl(111 + row).getWidth()

        if xbmc.Player().isPlaying() == False:
            self.log('No video is playing, not adding buttons')
            self.closeEPG()
            return False

        # go through all of the buttons and remove them
        for button in self.channelButtons[row]:
            self.removeControl(button)

        del self.channelButtons[row][:]

        # if the channel is paused, then only 1 button needed
        if self.MyOverlayWindow.channels[curchannel - 1].isPaused:
            self.channelButtons[row].append(xbmcgui.ControlButton(basex, basey, basew, baseh, self.MyOverlayWindow.channels[curchannel - 1].getCurrentTitle()), alignment=8)
            self.addControl(self.channelButtons[row][0])
        else:
            # Find the show that was running at the given time
            # Use the current time and show offset to calculate it
            # At timedif time, channelShowPosition was playing at channelTimes
            # The only way this isn't true is if the current channel is curchannel since
            # it could have been fast forwarded or rewinded (rewound)?
            if curchannel == self.MyOverlayWindow.currentChannel:
                playlistpos = int(xbmc.PlayList(xbmc.PLAYLIST_VIDEO).getposition())
                videotime = xbmc.Player().getTime()
                reftime = time.time()
            else:
                playlistpos = self.MyOverlayWindow.channels[curchannel - 1].playlistPosition
                videotime = self.MyOverlayWindow.channels[curchannel - 1].showTimeOffset
                reftime = self.MyOverlayWindow.channels[curchannel - 1].lastAccessTime

            # normalize reftime to the beginning of the video
            reftime -= videotime

            while reftime > starttime:
                playlistpos -= 1
                # No need to check bounds on the playlistpos, the duration function makes sure it is correct
                reftime -= self.MyOverlayWindow.channels[curchannel - 1].getItemDuration(playlistpos)

            while reftime + self.MyOverlayWindow.channels[curchannel - 1].getItemDuration(playlistpos) < starttime:
                reftime += self.MyOverlayWindow.channels[curchannel - 1].getItemDuration(playlistpos)
                playlistpos += 1

            # create a button for each show that runs in the next hour and a half
            endtime = starttime + 5400
            totaltime = 0

            while reftime < endtime:
                xpos = int(basex + (totaltime * (basew / 5400.0)))
                tmpdur = self.MyOverlayWindow.channels[curchannel - 1].getItemDuration(playlistpos)
                shouldskip = False

                # this should only happen the first time through this loop
                # it shows the small portion of the show before the current one
                if reftime < starttime:
                    tmpdur -= starttime - reftime
                    reftime = starttime

                    if tmpdur < 60 * 3:
                        shouldskip = True

                width = int((basew / 5400.0) * tmpdur)

                if width + xpos > 1280:
                    width = 1280 - xpos

                if shouldskip == False and width > 10:
                    self.channelButtons[row].append(xbmcgui.ControlButton(xpos, basey, width, baseh, self.MyOverlayWindow.channels[curchannel - 1].getItemTitle(playlistpos), alignment=8))
                    self.addControl(self.channelButtons[row][-1])

                totaltime += tmpdur
                reftime += tmpdur
                playlistpos += 1

        self.log('setButtons return')
        return True


    def onAction(self, act):
        self.log('onAction ' + str(act.getId()))

        if self.actionSemaphore.acquire(False) == False:
            self.log('Unable to get semaphore')
            return

        action = act.getId()

        if action == ACTION_PREVIOUS_MENU:
            self.closeEPG()
        elif action == ACTION_MOVE_DOWN:
            self.GoDown()
        elif action == ACTION_MOVE_UP:
            self.GoUp()
        elif action == ACTION_MOVE_LEFT:
            self.GoLeft()
        elif action == ACTION_MOVE_RIGHT:
            self.GoRight()
        elif action == ACTION_STOP:
            self.closeEPG()
            self.MyOverlayWindow.end()

        self.actionSemaphore.release()
        self.log('onAction return')


    def closeEPG(self):
        self.log('closeEPG')

        try:
            self.MyOverlayWindow.startSleepTimer()
        except:
            pass

        self.close()


    def onControl(self, control):
        self.log('onControl')


    # Run when a show is selected, so close the epg and run the show
    def onClick(self, controlid):
        self.log('onClick')

        if self.actionSemaphore.acquire(False) == False:
            self.log('Unable to get semaphore')
            return

        selectedbutton = self.getControl(controlid)

        for i in range(5):
            for x in range(len(self.channelButtons[i])):
                if selectedbutton == self.channelButtons[i][x]:
                    self.focusRow = i
                    self.focusIndex = x
                    self.selectShow()
                    self.closeEPG()
                    self.actionSemaphore.release()
                    self.log('onClick found button return')
                    return

        self.closeEPG()
        self.actionSemaphore.release()
        self.log('onClick return')


    def GoDown(self):
        self.log('goDown')

        # change controls to display the proper junks
        if self.focusRow == 4:
            self.setChannelButtons(self.shownTime, self.centerChannel + 1)
            self.focusRow = 3

        self.setProperButton(self.focusRow + 1)
        self.log('goDown return')


    def GoUp(self):
        self.log('goUp')

        # same as godown
        # change controls to display the proper junks
        if self.focusRow == 0:
            self.setChannelButtons(self.shownTime, self.centerChannel - 1)
            self.focusRow = 1

        self.setProperButton(self.focusRow - 1)
        self.log('goUp return')


    def GoLeft(self):
        self.log('goLeft')

        # change controls to display the proper junks
        if self.focusIndex == 0:
            self.setChannelButtons(self.shownTime - 1800, self.centerChannel)

        self.focusTime -= 60
        self.setProperButton(self.focusRow, True)
        self.log('goLeft return')


    def GoRight(self):
        self.log('goRight')

        # change controls to display the proper junks
        if self.focusIndex == len(self.channelButtons[self.focusRow]) - 1:
            self.setChannelButtons(self.shownTime + 1800, self.centerChannel)

        self.focusTime = self.focusEndTime + 30
        self.setProperButton(self.focusRow, True)
        self.log('goRight return')


    # based on the current focus row and index, find the appropriate button in
    # the new row to set focus to
    def setProperButton(self, newrow, resetfocustime = False):
        self.log('setProperButton ' + str(newrow))
        self.focusRow = newrow
        basex, basey = self.getControl(111 + newrow).getPosition()
        baseh = self.getControl(111 + newrow).getHeight()
        basew = self.getControl(111 + newrow).getWidth()

        for i in range(len(self.channelButtons[newrow])):
            left, top = self.channelButtons[newrow][i].getPosition()
            width = self.channelButtons[newrow][i].getWidth()
            left = left - basex
            starttime = self.shownTime + (left / (basew / 5400.0))
            endtime = starttime + (width / (basew / 5400.0))

            if self.focusTime >= starttime and self.focusTime <= endtime:
                self.focusIndex = i
                self.setFocus(self.channelButtons[newrow][i])
                self.setShowInfo()
                self.focusEndTime = endtime

                if resetfocustime:
                    self.focusTime = starttime + 30

                self.log('setProperButton found button return')
                return

        self.focusIndex = 0
        self.setFocus(self.channelButtons[newrow][0])
        left, top = self.channelButtons[newrow][0].getPosition()
        width = self.channelButtons[newrow][0].getWidth()
        left = left - basex
        starttime = self.shownTime + (left / (basew / 5400.0))
        endtime = starttime + (width / (basew / 5400.0))
        self.focusEndTime = endtime

        if resetfocustime:
            self.focusTime = starttime + 30

        self.setShowInfo()
        self.log('setProperButton return')


    def setShowInfo(self):
        self.log('setShowInfo')
        basex, basey = self.getControl(111 + self.focusRow).getPosition()
        baseh = self.getControl(111 + self.focusRow).getHeight()
        basew = self.getControl(111 + self.focusRow).getWidth()
        # use the selected time to set the video
        left, top = self.channelButtons[self.focusRow][self.focusIndex].getPosition()
        width = self.channelButtons[self.focusRow][self.focusIndex].getWidth()
        left = left - basex + (width / 2)
        starttime = self.shownTime + (left / (basew / 5400.0))
        newchan = self.MyOverlayWindow.fixChannel(self.centerChannel + self.focusRow - 2)
        plpos = self.determinePlaylistPosAtTime(starttime, newchan)

        if plpos == -1:
            self.log('Unable to find the proper playlist to set from EPG')
            return

        self.getControl(500).setLabel(self.MyOverlayWindow.channels[newchan - 1].getItemTitle(plpos))
        self.getControl(501).setLabel(self.MyOverlayWindow.channels[newchan - 1].getItemEpisodeTitle(plpos))
        self.getControl(502).setLabel(self.MyOverlayWindow.channels[newchan - 1].getItemDescription(plpos))
        self.log('setShowInfo return')


    # using the currently selected button, play the proper shows
    def selectShow(self):
        self.log('selectShow')
        basex, basey = self.getControl(111 + self.focusRow).getPosition()
        baseh = self.getControl(111 + self.focusRow).getHeight()
        basew = self.getControl(111 + self.focusRow).getWidth()
        # use the selected time to set the video
        left, top = self.channelButtons[self.focusRow][self.focusIndex].getPosition()
        width = self.channelButtons[self.focusRow][self.focusIndex].getWidth()
        left = left - basex + (width / 2)
        starttime = self.shownTime + (left / (basew / 5400.0))
        newchan = self.MyOverlayWindow.fixChannel(self.centerChannel + self.focusRow - 2)
        plpos = self.determinePlaylistPosAtTime(starttime, newchan)

        if plpos == -1:
            self.log('Unable to find the proper playlist to set from EPG')
            return

        if self.MyOverlayWindow.channels[newchan - 1].playlistPosition != plpos:
            self.MyOverlayWindow.channels[newchan - 1].setShowPosition(plpos)
            self.MyOverlayWindow.channels[newchan - 1].setShowTime(0)
            self.MyOverlayWindow.channels[newchan - 1].setAccessTime(time.time())

        self.MyOverlayWindow.newChannel = newchan
        self.log('selectShow return')


    def determinePlaylistPosAtTime(self, starttime, channel):
        self.log('determinePlaylistPosAtTime ' + str(starttime) + ', ' + str(channel))
        channel = self.MyOverlayWindow.fixChannel(channel)

        # if the channel is paused, then it's just the current item
        if self.MyOverlayWindow.channels[channel - 1].isPaused:
            self.log('determinePlaylistPosAtTime paused return')
            return self.MyOverlayWindow.channels[channel - 1].playlistPosition
        else:
            # Find the show that was running at the given time
            # Use the current time and show offset to calculate it
            # At timedif time, channelShowPosition was playing at channelTimes
            # The only way this isn't true is if the current channel is curchannel since
            # it could have been fast forwarded or rewinded (rewound)?
            if channel == self.MyOverlayWindow.currentChannel:
                playlistpos = xbmc.PlayList(xbmc.PLAYLIST_VIDEO).getposition()
                videotime = xbmc.Player().getTime()
                reftime = time.time()
            else:
                playlistpos = self.MyOverlayWindow.channels[channel - 1].playlistPosition
                videotime = self.MyOverlayWindow.channels[channel - 1].showTimeOffset
                reftime = self.MyOverlayWindow.channels[channel - 1].lastAccessTime

            # normalize reftime to the beginning of the video
            reftime -= videotime

            while reftime > starttime:
                playlistpos -= 1
                reftime -= self.MyOverlayWindow.channels[channel - 1].getItemDuration(playlistpos)

            while reftime + self.MyOverlayWindow.channels[channel - 1].getItemDuration(playlistpos) < starttime:
                reftime += self.MyOverlayWindow.channels[channel - 1].getItemDuration(playlistpos)
                playlistpos += 1

            self.log('determinePlaylistPosAtTime return' + str(self.MyOverlayWindow.channels[channel - 1].fixPlaylistIndex(playlistpos)))
            return self.MyOverlayWindow.channels[channel - 1].fixPlaylistIndex(playlistpos)
