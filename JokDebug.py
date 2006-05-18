# This class provides a bunch of debugging methods that are mainly intended for cracking open pipelines and
# looking at the goo inside. This most likely won't be shipped with the final release and is mainly useful for
# hackers who are involved in the project.
#
# To enable debugging mode, set an environmental variable:
#
#    JOKOSHER_DEBUG=1

import pygst
pygst.require("0.10")
import gst
import gtk

class JokDebug:
    def __init__(self):
        # remember the trailing space
        self.DEBUG_PREFIX = "[debug] "

    def ShowPipelineDetails(self, pipeline):
        '''Display the pipeline details, including pads'''

        pipechildren = []

        pipe = pipeline.sorted()

        pipelinechildren = []
        finalpipe = ""

        for element in pipeline.sorted():
            pipelinechildren[:0] = element

        for child in pipe:
            print self.DEBUG_PREFIX + ">>> Element '" + str(child.get_name()) + "' (" + child.get_factory().get_name() + ")"
            for pad in child.pads():
                if pad.is_linked() == True:
                    print self.DEBUG_PREFIX + "\tPAD LINK: pad: '" + str(pad.get_name()) + "' connects to " + str(pad.get_peer())
                else:
                    print self.DEBUG_PREFIX + "\tNO LINK: " + str(pad.get_name())

            print self.DEBUG_PREFIX + "<<< END ELEMENT <<<"

    def ShowPipeline(self, pipeline):
        '''Display the construction of the pipeline in a gst-launch type format'''

        pipelinechildren = []
        finalpipe = ""

        for element in pipeline.sorted():
            pipelinechildren[:0] = [element.get_factory().get_name()]

        for elem in pipelinechildren:
            finalpipe += elem  + " ! "

        print self.DEBUG_PREFIX + finalpipe

    def ShowPipelineTree(self, pipeline):
        '''Display a tree of pipeline elements and their children'''

        pipechildren = []

        pipe = pipeline.sorted()

        pipelinechildren = []
        finalpipe = ""

        print self.DEBUG_PREFIX + "PIPELINE END"
        for element in pipeline.sorted():
            try:
                childelements = element.elements()
                print self.DEBUG_PREFIX + element.get_factory().get_name()

                for el in childelements:
                    print self.DEBUG_PREFIX + "\t" + el.get_factory().get_name()

                    try:
                        grandchildelements = el.elements()
                        
                        for gel in grandchildelements:
                            print self.DEBUG_PREFIX + "\t\t" + gel.get_factory().get_name()

                            try:
                                grgrandchildelements = gel.elements()
                        
                                for gel in grgrandchildelements:
                                    print self.DEBUG_PREFIX + "\t\t\t" + gel.get_factory().get_name()
                            except:
                                pass     
                    except:
                        pass
            except:
                print self.DEBUG_PREFIX + element.get_factory().get_name()

        print self.DEBUG_PREFIX + "PIPELINE START"
                