#
#    THIS FILE IS PART OF THE JOKOSHER PROJECT AND LICENSED UNDER THE GPL. SEE
#    THE 'COPYING' FILE FOR DETAILS
#
#    NewDialog.py
#
#    This class provides a bunch of debugging methods that are mainly intended
#    for cracking open pipelines and looking at the goo inside. This most likely
#    won't be shipped with the final release and is mainly useful for hackers
#    who are involved in the project.
#
#    To enable debugging mode, set an environmental variable:
#
#       foo@bar~$ export JOKOSHER_DEBUG=1
#
#-------------------------------------------------------------------------------
import Globals
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
            Globals.debug(self.DEBUG_PREFIX + ">>> Element '" + str(child.get_name()) + "' (" + child.get_factory().get_name() + ")")
            for pad in child.pads():
                if pad.is_linked() == True:
                    Globals.debug(self.DEBUG_PREFIX + "\tPAD LINK: pad: '" + str(pad.get_name()) + "' connects to " + str(pad.get_peer()))
                else:
                    Globals.debug(self.DEBUG_PREFIX + "\tNO LINK: " + str(pad.get_name()))

            Globals.debug(self.DEBUG_PREFIX + "<<< END ELEMENT <<<")

    def ShowPipeline(self, pipeline):
        '''Display the construction of the pipeline in a gst-launch type format'''

        pipelinechildren = []
        finalpipe = ""

        for element in pipeline.sorted():
            pipelinechildren[:0] = [element.get_factory().get_name()]

        for elem in pipelinechildren:
            finalpipe += elem  + " ! "

        Globals.debug(self.DEBUG_PREFIX + finalpipe)

    def ShowPipelineTree(self, pipeline, recurseDepth = 0, maxDepth = 3):
        '''Display a tree of pipeline elements and their children'''
        if recurseDepth > maxDepth:
            return

        if recurseDepth == 0:
            Globals.debug(self.DEBUG_PREFIX + "PIPELINE END")

        for element in pipeline.sorted():
            try:
                indent = self.DEBUG_PREFIX
                for i in range(recurseDepth):
                    indent += "\t"
                Globals.debug(indent + element.get_factory().get_name() + ": " + element.get_name())

                self.ShowPipelineTree(element, recurseDepth+1, maxDepth)
            except:
                pass

        if recurseDepth == 0:
            Globals.debug(self.DEBUG_PREFIX + "PIPELINE START")
                
