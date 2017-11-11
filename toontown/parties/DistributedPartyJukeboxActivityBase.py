# File: t (Python 2.4)

from direct.actor.Actor import Actor
from direct.task.Task import Task
from pandac.PandaModules import *
from otp.otpbase.OTPBase import OTPBase
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
from toontown.parties.DistributedPartyActivity import DistributedPartyActivity
from toontown.parties.PartyGlobals import ActivityIds, ActivityTypes, JUKEBOX_TIMEOUT
from toontown.parties.PartyGlobals import getMusicRepeatTimes, MUSIC_PATH, sanitizePhase
from toontown.parties.JukeboxGui import JukeboxGui

class DistributedPartyJukeboxActivityBase(DistributedPartyActivity):
    notify = directNotify.newCategory('DistributedPartyJukeboxActivityBase')
    
    def __init__(self, cr, actId, phaseToMusicData):
        DistributedPartyActivity.__init__(self, cr, actId, ActivityTypes.Continuous)
        self.phaseToMusicData = phaseToMusicData
        self.jukebox = None
        self.gui = None
        self.tunes = []
        self.music = None
        self.currentSongData = None
        self.localQueuedSongInfo = None
        self.localQueuedSongListItem = None

    
    def generateInit(self):
        self.gui = JukeboxGui(self.phaseToMusicData)

    
    def load(self):
        DistributedPartyActivity.load(self)
        self.jukebox = Actor('phase_13/models/parties/jukebox_model', {
            'dance': 'phase_13/models/parties/jukebox_dance' })
        self.jukebox.reparentTo(self.root)
        self.collNode = CollisionNode(self.getCollisionName())
        self.collNode.setCollideMask(ToontownGlobals.CameraBitmask | ToontownGlobals.WallBitmask)
        collTube = CollisionTube(0, 0, 0, 0.0, 0.0, 4.25, 2.25)
        collTube.setTangible(1)
        self.collNode.addSolid(collTube)
        self.collNodePath = self.jukebox.attachNewNode(self.collNode)
        self.sign.setPos(-5.0, 0, 0)
        self.activate()

    
    def unload(self):
        DistributedPartyActivity.unload(self)
        self.gui.unload()
        if self.music is not None:
            self.music.stop()
        
        self.jukebox.stop()
        self.jukebox.delete()
        self.jukebox = None
        self.ignoreAll()

    
    def getCollisionName(self):
        return self.uniqueName('jukeboxCollision')

    
    def activate(self):
        self.accept('enter' + self.getCollisionName(), self._DistributedPartyJukeboxActivityBase__handleEnterCollision)

    
    def _DistributedPartyJukeboxActivityBase__handleEnterCollision(self, collisionEntry):
        if base.cr.playGame.getPlace().fsm.getCurrentState().getName() == 'walk':
            base.cr.playGame.getPlace().fsm.request('activity')
            self.d_toonJoinRequest()
        

    
    def joinRequestDenied(self, reason):
        DistributedPartyActivity.joinRequestDenied(self, reason)
        self.showMessage(TTLocalizer.PartyJukeboxOccupied)

    
    def handleToonJoined(self, toonId):
        toon = base.cr.doId2do.get(toonId)
        if toon:
            self.jukebox.lookAt(base.cr.doId2do[toonId])
            self.jukebox.setHpr(self.jukebox.getH() + 180.0, 0, 0)
        
        if toonId == base.localAvatar.doId:
            self._DistributedPartyJukeboxActivityBase__localUseJukebox()
        

    
    def handleToonExited(self, toonId):
        if toonId == base.localAvatar.doId and self.gui.isLoaded():
            self._DistributedPartyJukeboxActivityBase__deactivateGui()
        

    
    def handleToonDisabled(self, toonId):
        self.notify.warning('handleToonDisabled no implementation yet')

    
    def _DistributedPartyJukeboxActivityBase__localUseJukebox(self):
        base.localAvatar.disableAvatarControls()
        base.localAvatar.stopPosHprBroadcast()
        self._DistributedPartyJukeboxActivityBase__activateGui()
        self.accept(JukeboxGui.CLOSE_EVENT, self._DistributedPartyJukeboxActivityBase__handleGuiClose)
        taskMgr.doMethodLater(0.5, self._DistributedPartyJukeboxActivityBase__localToonWillExitTask, self.uniqueName('toonWillExitJukeboxOnTimeout'), extraArgs = None)
        self.accept(JukeboxGui.ADD_SONG_CLICK_EVENT, self._DistributedPartyJukeboxActivityBase__handleQueueSong)
        if self.isUserHost():
            self.accept(JukeboxGui.MOVE_TO_TOP_CLICK_EVENT, self._DistributedPartyJukeboxActivityBase__handleMoveSongToTop)
        

    
    def _DistributedPartyJukeboxActivityBase__localToonWillExitTask(self, task):
        self.localToonExiting()
        return Task.done

    
    def _DistributedPartyJukeboxActivityBase__activateGui(self):
        self.gui.enable(timer = JUKEBOX_TIMEOUT)
        self.gui.disableAddSongButton()
        if self.currentSongData is not None:
            self.gui.setSongCurrentlyPlaying(self.currentSongData[0], self.currentSongData[1])
        
        self.d_queuedSongsRequest()

    
    def _DistributedPartyJukeboxActivityBase__deactivateGui(self):
        self.ignore(JukeboxGui.CLOSE_EVENT)
        self.ignore(JukeboxGui.SONG_SELECT_EVENT)
        self.ignore(JukeboxGui.MOVE_TO_TOP_CLICK_EVENT)
        base.cr.playGame.getPlace().setState('walk')
        base.localAvatar.startPosHprBroadcast()
        base.localAvatar.enableAvatarControls()
        self.gui.unload()
        self._DistributedPartyJukeboxActivityBase__localClearQueuedSong()

    
    def isUserHost(self):
        return self.party.partyInfo.hostId == base.localAvatar.doId

    
    def d_queuedSongsRequest(self):
        self.sendUpdate('queuedSongsRequest')

    
    def queuedSongsResponse(self, songInfoList, index):
        if self.gui.isLoaded():
            for i in range(len(songInfoList)):
                songInfo = songInfoList[i]
                if index >= 0:
                    pass
                self._DistributedPartyJukeboxActivityBase__addSongToQueue(songInfo, isLocalQueue = i == index)
            
            self.gui.enableAddSongButton()
        

    
    def _DistributedPartyJukeboxActivityBase__handleGuiClose(self):
        self._DistributedPartyJukeboxActivityBase__deactivateGui()
        self.d_toonExitDemand()

    
    def _DistributedPartyJukeboxActivityBase__handleQueueSong(self, name, values):
        self.d_setNextSong(values[0], values[1])

    
    def d_setNextSong(self, phase, filename):
        self.sendUpdate('setNextSong', [
            (phase, filename)])

    
    def setSongInQueue(self, songInfo):
        if self.gui.isLoaded():
            phase = sanitizePhase(songInfo[0])
            filename = songInfo[1]
            data = self.getMusicData(phase, filename)
            if data:
                if self.localQueuedSongListItem is not None:
                    self.localQueuedSongListItem['text'] = data[0]
                else:
                    self._DistributedPartyJukeboxActivityBase__addSongToQueue(songInfo, isLocalQueue = True)
            
        

    
    def _DistributedPartyJukeboxActivityBase__addSongToQueue(self, songInfo, isLocalQueue = False):
        if isLocalQueue:
            pass
        isHost = self.isUserHost()
        data = self.getMusicData(sanitizePhase(songInfo[0]), songInfo[1])
        if data:
            listItem = self.gui.addSongToQueue(data[0], highlight = isLocalQueue, moveToTopButton = isHost)
            if isLocalQueue:
                self.localQueuedSongInfo = songInfo
                self.localQueuedSongListItem = listItem
            
        

    
    def _DistributedPartyJukeboxActivityBase__localClearQueuedSong(self):
        self.localQueuedSongInfo = None
        self.localQueuedSongListItem = None

    
    def _DistributedPartyJukeboxActivityBase__play(self, phase, filename, length):
        self.music = base.loadMusic((MUSIC_PATH + '%s') % (phase, filename))
        if self.music:
            if self._DistributedPartyJukeboxActivityBase__checkPartyValidity() and hasattr(base.cr.playGame.getPlace().loader, 'music') and base.cr.playGame.getPlace().loader.music:
                base.cr.playGame.getPlace().loader.music.stop()
            
            base.resetMusic.play()
            self.music.setTime(0.0)
            self.music.setLoopCount(getMusicRepeatTimes(length))
            self.music.play()
            jukeboxAnimControl = self.jukebox.getAnimControl('dance')
            if not jukeboxAnimControl.isPlaying():
                self.jukebox.loop('dance')
            
            self.currentSongData = (phase, filename)
        

    
    def _DistributedPartyJukeboxActivityBase__stop(self):
        self.jukebox.stop()
        self.currentSongData = None
        if self.music:
            self.music.stop()
        
        if self.gui.isLoaded():
            self.gui.clearSongCurrentlyPlaying()
        

    
    def setSongPlaying(self, songInfo, toonId):
        phase = sanitizePhase(songInfo[0])
        filename = songInfo[1]
        if not filename:
            self._DistributedPartyJukeboxActivityBase__stop()
            return None
        
        data = self.getMusicData(phase, filename)
        if data:
            self._DistributedPartyJukeboxActivityBase__play(phase, filename, data[1])
            self.setSignNote(data[0])
            if self.gui.isLoaded():
                item = self.gui.popSongFromQueue()
                self.gui.setSongCurrentlyPlaying(phase, filename)
                if item == self.localQueuedSongListItem:
                    self._DistributedPartyJukeboxActivityBase__localClearQueuedSong()
                
            
        
        if toonId == localAvatar.doId:
            localAvatar.setSystemMessage(0, TTLocalizer.PartyJukeboxNowPlaying)
        

    
    def _DistributedPartyJukeboxActivityBase__handleMoveSongToTop(self):
        if self.isUserHost() and self.localQueuedSongListItem is not None:
            self.d_moveHostSongToTopRequest()
        

    
    def d_moveHostSongToTopRequest(self):
        self.notify.debug('d_moveHostSongToTopRequest')
        self.sendUpdate('moveHostSongToTopRequest')

    
    def moveHostSongToTop(self):
        self.notify.debug('moveHostSongToTop')
        if self.gui.isLoaded():
            self.gui.pushQueuedItemToTop(self.localQueuedSongListItem)
        

    
    def getMusicData(self, phase, filename):
        data = []
        phase = sanitizePhase(phase)
        phase = self.phaseToMusicData.get(phase)
        if phase:
            data = phase.get(filename, [])
        
        return data

    
    def _DistributedPartyJukeboxActivityBase__checkPartyValidity(self):
        if hasattr(base.cr.playGame, 'getPlace') and base.cr.playGame.getPlace() and hasattr(base.cr.playGame.getPlace(), 'loader') and base.cr.playGame.getPlace().loader:
            return True
        else:
            return False


