# -*- coding: utf-8 -*-
'''
Tests for messaging reliability

'''
# pylint: skip-file
# pylint: disable=C0103
import sys
if sys.version_info < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import os
import time
import tempfile
import shutil
from collections import deque

from ioflo.base.odicting import odict
from ioflo.base.aiding import Timer, StoreTimer, just
from ioflo.base import storing
from ioflo.base.consoling import getConsole
console = getConsole()

from raet import raeting, nacling
from raet.road import estating, keeping, stacking, packeting, transacting

if sys.platform == 'win32':
    TEMPDIR = 'c:/temp'
    if not os.path.exists(TEMPDIR):
        os.mkdir(TEMPDIR)
else:
    TEMPDIR = '/tmp'

def setUpModule():
    console.reinit(verbosity=console.Wordage.concise)

def tearDownModule():
    pass

class BasicTestCase(unittest.TestCase):
    """"""

    def setUp(self):
        self.store = storing.Store(stamp=0.0)
        self.timer = StoreTimer(store=self.store, duration=1.0)

        self.base = tempfile.mkdtemp(prefix="raet",  suffix="base", dir=TEMPDIR)

    def tearDown(self):
        if os.path.exists(self.base):
            shutil.rmtree(self.base)

    def createRoadData(self,
                       base,
                       name='',
                       ha=None,
                       main=None,
                       auto=raeting.autoModes.never,
                       role=None,
                       kind=None, ):
        '''
        Creates odict and populates with data to setup road stack

        '''
        data = odict()
        data['name'] = name
        data['ha'] = ha
        data['main'] =  main
        data['auto'] = auto
        data['role'] = role if role is not None else name
        data['kind'] = kind
        data['dirpath'] = os.path.join(base, 'road', 'keep', name)
        signer = nacling.Signer()
        data['sighex'] = signer.keyhex
        data['verhex'] = signer.verhex
        privateer = nacling.Privateer()
        data['prihex'] = privateer.keyhex
        data['pubhex'] = privateer.pubhex

        return data

    def createRoadStack(self,
                        data,
                        uid=None,
                        ha=None,
                        main=None,
                        auto=None,
                        role=None,
                        kind=None,
                        period=None,
                        offset=None,):
        '''
        Creates stack and local estate from data with
        and overrides with parameters

        returns stack

        '''
        stack = stacking.RoadStack(store=self.store,
                                   name=data['name'],
                                   uid=uid,
                                   ha=ha or data['ha'],
                                   main=main if main is not None else data['main'],
                                   role=role if role is not None else data['role'],
                                   sigkey=data['sighex'],
                                   prikey=data['prihex'],
                                   auto=auto if auto is not None else data['auto'],
                                   kind=kind if kind is not None else data['kind'],
                                   dirpath=data['dirpath'],
                                   period=period,
                                   offset=offset,)

        return stack

    def join(self, initiator, correspondent, deid=None, duration=1.0,
                cascade=False):
        '''
        Utility method to do join. Call from test method.
        '''
        console.terse("\nJoin Transaction **************\n")
        if not initiator.remotes:
            initiator.addRemote(estating.RemoteEstate(stack=initiator,
                                                      fuid=0, # vacuous join
                                                      sid=0, # always 0 for join
                                                      ha=correspondent.local.ha))
        initiator.join(uid=deid, cascade=cascade)
        self.serviceStacks([correspondent, initiator], duration=duration)

    def allow(self, initiator, correspondent, deid=None, duration=1.0,
                cascade=False):
        '''
        Utility method to do allow. Call from test method.
        '''
        console.terse("\nAllow Transaction **************\n")
        initiator.allow(uid=deid, cascade=cascade)
        self.serviceStacks([correspondent, initiator], duration=duration)

    def alive(self, initiator, correspondent, duid=None, duration=1.0,
                cascade=False):
        '''
        Utility method to do alive. Call from test method.
        '''
        console.terse("\nAlive Transaction **************\n")
        initiator.alive(uid=duid, cascade=cascade)
        self.serviceStacks([correspondent, initiator], duration=duration)

    def message(self, msgs, initiator, correspondent, duration=2.0):
        '''
        Utility to send messages both ways
        '''
        for msg in msgs:
            initiator.transmit(msg)

        self.serviceStacks([initiator, correspondent], duration=duration)

    def flushReceives(self, stack):
        '''
        Flush any queued up udp packets in receive buffer
        '''
        stack.serviceReceives()
        stack.rxes.clear()

    def dupReceives(self, stack):
        '''
        Duplicate each queued up udp packet in receive buffer
        '''
        stack.serviceReceives()
        rxes = stack.rxes
        stack.rxes = deque()
        for rx in rxes:
            stack.rxes.append(rx) # one
            stack.rxes.append(rx) # and one more

    def serviceStack(self, stack, duration=1.0):
        '''
        Utility method to service queues for one stack. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            stack.serviceAll()
            if not (stack.transactions):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def serviceStacks(self, stacks, duration=1.0):
        '''
        Utility method to service queues for list of stacks. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            for stack in stacks:
                stack.serviceAll()
            if all([not stack.transactions for stack in stacks]):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def serviceStacksWithDrops(self, stacks, drops=None, duration=1.0):
        '''
        Utility method to service queues for list of stacks. Call from test method.
        Drops tx msgs in .txes deque based on drops filter which is list
        of truthy falsey values. For each element of drops if truthy then drop
        the tx at the corresponding index for each service of the txes deque.
        '''
        if drops is None:
            drops = []
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            for stack in stacks:
                stack.serviceTxMsgs()
                drops = [drop for drop in just(len(stack.txes), drops)]  # make drops length oftxCnt None fill
                i = 0
                while stack.txes:
                    if drops[i]:
                        stack.txes.popleft()  # pop and drop
                        console.concise("Stack {0}: Dropping {1}\n".format(stack.name, i))
                    else:
                        stack.serviceTxOnce() # service
                    i += 1

            time.sleep(0.05)
            for stack in stacks:
                stack.serviceAllRx()

            if all([not stack.transactions for stack in stacks]):
                break
            drops = []
            self.store.advanceStamp(0.1)
            time.sleep(0.05)

    def serviceStacksDropAllTx(self, stacks, duration=1.0):
        '''
        Utility method to service queues for list of stacks. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            for stack in stacks:
                stack.serviceTxMsgs()
                stack.serviceTxes()
                self.txes.clear()
                stack.serviceReceives()
                stack.serviceRxes()
                stack.process()

            if all([not stack.transactions for stack in stacks]):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def serviceStacksDropAllRx(self, stacks, duration=1.0):
        '''
        Utility method to service queues for list of stacks. Call from test method.
        '''
        self.timer.restart(duration=duration)
        while not self.timer.expired:
            for stack in stacks:
                stack.serviceReceives()
                stack.rxes.clear()
                stack.serviceRxes()
                stack.process()
                stack.serviceAllTx()
            if all([not stack.transactions for stack in stacks]):
                break
            self.store.advanceStamp(0.1)
            time.sleep(0.1)

    def testMessageBurstZero(self):
        '''
        Test message with burst limit of 0, that is, no limit
        '''
        console.terse("{0}\n".format(self.testMessageBurstZero.__doc__))

        alphaData = self.createRoadData(name='alpha',
                                        base=self.base,
                                        auto=raeting.autoModes.once)
        keeping.clearAllKeep(alphaData['dirpath'])
        alpha = self.createRoadStack(data=alphaData,
                                     main=True,
                                     auto=alphaData['auto'],
                                     ha=None)

        betaData = self.createRoadData(name='beta',
                                       base=self.base,
                                       auto=raeting.autoModes.once)
        keeping.clearAllKeep(betaData['dirpath'])
        beta = self.createRoadStack(data=betaData,
                                    main=True,
                                    auto=betaData['auto'],
                                    ha=("", raeting.RAET_TEST_PORT))

        console.terse("\nJoin *********\n")
        self.join(alpha, beta) # vacuous join fails because other not main
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, None)
            self.assertIs(remote.alived, None)

        console.terse("\nAllow *********\n")
        self.allow(alpha, beta)
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, True)
            self.assertIs(remote.alived, True)  # fast alive

        stacking.RoadStack.BurstSize = 0

        console.terse("\nMessage Alpha to Beta *********\n")
        msgs = []
        bloat = []
        for i in range(300):
            bloat.append(str(i).rjust(100, " "))
        bloat = "".join(bloat)
        sentMsg = odict(who="Green", data=bloat)
        msgs.append(sentMsg)

        self.message(msgs, alpha, beta, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage Beta to Alpha *********\n")
        self.message(msgs, beta, alpha, duration=5.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        stacking.RoadStack.BurstSize = 0
        for stack in [alpha, beta]:
            stack.server.close()
            stack.clearAllKeeps()

    def testMessageBurstOne(self):
        '''
        Test message with burst limit of 1
        '''
        console.terse("{0}\n".format(self.testMessageBurstOne.__doc__))

        alphaData = self.createRoadData(name='alpha',
                                        base=self.base,
                                        auto=raeting.autoModes.once)
        keeping.clearAllKeep(alphaData['dirpath'])
        alpha = self.createRoadStack(data=alphaData,
                                     main=True,
                                     auto=alphaData['auto'],
                                     ha=None)

        betaData = self.createRoadData(name='beta',
                                       base=self.base,
                                       auto=raeting.autoModes.once)
        keeping.clearAllKeep(betaData['dirpath'])
        beta = self.createRoadStack(data=betaData,
                                    main=True,
                                    auto=betaData['auto'],
                                    ha=("", raeting.RAET_TEST_PORT))

        console.terse("\nJoin *********\n")
        self.join(alpha, beta) # vacuous join fails because other not main
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, None)
            self.assertIs(remote.alived, None)

        console.terse("\nAllow *********\n")
        self.allow(alpha, beta)
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, True)
            self.assertIs(remote.alived, True)  # fast alive

        stacking.RoadStack.BurstSize = 1

        console.terse("\nMessage Alpha to Beta *********\n")
        msgs = []
        bloat = []
        for i in range(300):
            bloat.append(str(i).rjust(100, " "))
        bloat = "".join(bloat)
        sentMsg = odict(who="Green", data=bloat)
        msgs.append(sentMsg)

        self.message(msgs, alpha, beta, duration=10.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage Beta to Alpha *********\n")
        self.message(msgs, beta, alpha, duration=10.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        stacking.RoadStack.BurstSize = 0
        for stack in [alpha, beta]:
            stack.server.close()
            stack.clearAllKeeps()

    def testMessageBurstEleven(self):
        '''
        Test message with burst limit of 11
        '''
        console.terse("{0}\n".format(self.testMessageBurstEleven.__doc__))

        alphaData = self.createRoadData(name='alpha',
                                        base=self.base,
                                        auto=raeting.autoModes.once)
        keeping.clearAllKeep(alphaData['dirpath'])
        alpha = self.createRoadStack(data=alphaData,
                                     main=True,
                                     auto=alphaData['auto'],
                                     ha=None)

        betaData = self.createRoadData(name='beta',
                                       base=self.base,
                                       auto=raeting.autoModes.once)
        keeping.clearAllKeep(betaData['dirpath'])
        beta = self.createRoadStack(data=betaData,
                                    main=True,
                                    auto=betaData['auto'],
                                    ha=("", raeting.RAET_TEST_PORT))

        console.terse("\nJoin *********\n")
        self.join(alpha, beta) # vacuous join fails because other not main
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, None)
            self.assertIs(remote.alived, None)

        console.terse("\nAllow *********\n")
        self.allow(alpha, beta)
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, True)
            self.assertIs(remote.alived, True)  # fast alive

        stacking.RoadStack.BurstSize = 1

        console.terse("\nMessage Alpha to Beta *********\n")
        msgs = []
        bloat = []
        for i in range(300):
            bloat.append(str(i).rjust(100, " "))
        bloat = "".join(bloat)
        sentMsg = odict(who="Green", data=bloat)
        msgs.append(sentMsg)

        self.message(msgs, alpha, beta, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage Beta to Alpha *********\n")
        self.message(msgs, beta, alpha, duration=5.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        stacking.RoadStack.BurstSize = 0
        for stack in [alpha, beta]:
            stack.server.close()
            stack.clearAllKeeps()

    def testMessageWithDrops(self):
        '''
        Test message with packets dropped
        '''
        console.terse("{0}\n".format(self.testMessageWithDrops.__doc__))

        alphaData = self.createRoadData(name='alpha',
                                       base=self.base,
                                       auto=raeting.autoModes.once)
        keeping.clearAllKeep(alphaData['dirpath'])
        alpha = self.createRoadStack(data=alphaData,
                                     main=True,
                                     auto=alphaData['auto'],
                                     ha=None)

        betaData = self.createRoadData(name='beta',
                                        base=self.base,
                                        auto=raeting.autoModes.once)
        keeping.clearAllKeep(betaData['dirpath'])
        beta = self.createRoadStack(data=betaData,
                                     main=True,
                                     auto=betaData['auto'],
                                     ha=("", raeting.RAET_TEST_PORT))

        console.terse("\nJoin *********\n")
        self.join(alpha, beta) # vacuous join fails because other not main
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, None)
            self.assertIs(remote.alived, None)

        console.terse("\nAllow *********\n")
        self.allow(alpha, beta)
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, True)
            self.assertIs(remote.alived, True)  # fast alive

        console.terse("\nMessage Alpha to Beta *********\n")
        msgs = []
        bloat = []
        for i in range(300):
            bloat.append(str(i).rjust(100, " "))
        bloat = "".join(bloat)
        sentMsg = odict(who="Green", data=bloat)
        msgs.append(sentMsg)

        self.message(msgs, alpha, beta, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage Beta to Alpha *********\n")
        self.message(msgs, beta, alpha, duration=5.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage with drops Alpha to Beta *********\n")
        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 0)
        alpha.transmit(sentMsg)

        drops = [0, 1, 1, 0, 0, 0, 0, 0, 1]
        #drops = []
        self.serviceStacksWithDrops([alpha, beta], drops=drops, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage with drops Beta to Alpha *********\n")
        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 0)
        beta.transmit(sentMsg)

        drops = [0, 1, 0, 0, 1, 0, 0, 0, 1]
        #drops = []
        self.serviceStacksWithDrops([alpha, beta], drops=drops, duration=5.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        for stack in [alpha, beta]:
            stack.server.close()
            stack.clearAllKeeps()

    def testMessageWithBurstDrops(self):
        '''
        Test message with packets dropped
        '''
        console.terse("{0}\n".format(self.testMessageWithBurstDrops.__doc__))

        alphaData = self.createRoadData(name='alpha',
                                        base=self.base,
                                        auto=raeting.autoModes.once)
        keeping.clearAllKeep(alphaData['dirpath'])
        alpha = self.createRoadStack(data=alphaData,
                                     main=True,
                                     auto=alphaData['auto'],
                                     ha=None)


        betaData = self.createRoadData(name='beta',
                                       base=self.base,
                                       auto=raeting.autoModes.once)
        keeping.clearAllKeep(betaData['dirpath'])
        beta = self.createRoadStack(data=betaData,
                                    main=True,
                                    auto=betaData['auto'],
                                    ha=("", raeting.RAET_TEST_PORT))

        stacking.RoadStack.BurstSize = 4

        console.terse("\nJoin *********\n")
        self.join(alpha, beta) # vacuous join fails because other not main
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, None)
            self.assertIs(remote.alived, None)

        console.terse("\nAllow *********\n")
        self.allow(alpha, beta)
        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)
            self.assertEqual(len(stack.remotes), 1)
            self.assertEqual(len(stack.nameRemotes), 1)
            remote = stack.remotes.values()[0]
            self.assertIs(remote.joined, True)
            self.assertIs(remote.allowed, True)
            self.assertIs(remote.alived, True)  # fast alive

        console.terse("\nMessage Alpha to Beta *********\n")
        msgs = []
        bloat = []
        for i in range(300):
            bloat.append(str(i).rjust(100, " "))
        bloat = "".join(bloat)
        sentMsg = odict(who="Green", data=bloat)
        msgs.append(sentMsg)

        self.message(msgs, alpha, beta, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage Beta to Alpha *********\n")
        self.message(msgs, beta, alpha, duration=5.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage with drops Alpha to Beta *********\n")
        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 0)
        alpha.transmit(sentMsg)

        drops = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 1]
        #drops = []
        self.serviceStacksWithDrops([alpha, beta], drops=drops, duration=5.0)

        for stack in [alpha, beta]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(alpha.txMsgs), 0)
        self.assertEqual(len(alpha.txes), 0)
        self.assertEqual(len(beta.rxes), 0)
        self.assertEqual(len(beta.rxMsgs), 1)
        receivedMsg, source = beta.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        console.terse("\nMessage with drops Beta to Alpha *********\n")
        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 0)
        beta.transmit(sentMsg)

        drops = [0, 1, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1]
        #drops = []
        self.serviceStacksWithDrops([alpha, beta], drops=drops, duration=5.0)

        for stack in [beta, alpha]:
            self.assertEqual(len(stack.transactions), 0)

        self.assertEqual(len(beta.txMsgs), 0)
        self.assertEqual(len(beta.txes), 0)
        self.assertEqual(len(alpha.rxes), 0)
        self.assertEqual(len(alpha.rxMsgs), 1)
        receivedMsg, source = alpha.rxMsgs.popleft()
        self.assertDictEqual(sentMsg, receivedMsg)

        stacking.RoadStack.BurstSize = 0
        for stack in [alpha, beta]:
            stack.server.close()
            stack.clearAllKeeps()


def runOne(test):
    '''
    Unittest Runner
    '''
    test = BasicTestCase(test)
    suite = unittest.TestSuite([test])
    unittest.TextTestRunner(verbosity=2).run(suite)

def runSome():
    '''
    Unittest runner
    '''
    tests =  []
    names = [
                'testMessageBurstZero',
                'testMessageBurstOne',
                'testMessageBurstEleven',
                'testMessageWithDrops',
                'testMessageWithBurstDrops',
            ]

    tests.extend(map(BasicTestCase, names))

    suite = unittest.TestSuite(tests)
    unittest.TextTestRunner(verbosity=2).run(suite)

def runAll():
    '''
    Unittest runner
    '''
    suite = unittest.TestSuite()
    suite.addTest(unittest.TestLoader().loadTestsFromTestCase(BasicTestCase))

    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__' and __package__ is None:

    #console.reinit(verbosity=console.Wordage.concise)

    #runAll() #run all unittests

    runSome()#only run some

    #runOne('testMessageBurstOne')