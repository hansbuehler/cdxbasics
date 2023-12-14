"""
crman
Managing \r updates
Hans Buehler 2023
"""

from .logger import Logger
_log = Logger(__file__)

class CRMan(object):
    """
    Carraige Return ('\r') manager.    
    This class is meant to enable efficient per-line updates using '\r' for text output with a focus on making it work with both Jupyter and the command shell.
    In particular, Jupyter does not support the ANSI \33[2K 'clear line' code.
    
        crman = CRMan()
        print( crman("\rmessage 111111"), end='' )
        print( crman("\rmessage 2222"), end='' )
        print( crman("\rmessage 33"), end='' )
        print( crman("\rmessage 1\n"), end='' )
        
        --> message 1     
        
        print( crman("\rmessage 111111"), end='' )
        print( crman("\rmessage 2222"), end='' )
        print( crman("\rmessage 33"), end='' )
        print( crman("\rmessage 1"), end='' )
        print( crman("... and more"), end='' )
        
        --> message 1... and more
    """
    
    def __init__(self):
        """ See help(CRMan) """
        self._current = ""
        
    def __call__(self, message : str) -> str:
        """
        Convert 'message' containing '\r' and '\n' into a printable string which ensures that '\r' string do not lead to printed artifacts.
        
        Parameters
        ----------
            message : str
                message containing \r and \n.
                
        Returns
        -------
            Printable string.
        """
        if message is None:
            return

        lines  = message.split('\n')
        output = ""
        
        # first line
        line   = lines[0]
        icr    = line.rfind('\r')
        if icr == -1:
            line = self._current + line
        else:
            line = line[icr+1:]
        if len(self._current) > 0:
            output    += '\r' + ' '*len(self._current) + '\r' + '\33[2K' + '\r'
        output        += line
        self._current = line
            
        if len(lines) > 1:
            output       += '\n'
            self._current = ""
            
            # intermediate lines
            for line in lines[1:-1]:
                # support multiple '\r', but in practise only the last one will be printed
                icr    =  line.rfind('\r')
                line   =  line if icr==-1 else line[icr+1:]
                output += line + '\n'
                
            # final line
            line      = lines[-1]
            if len(line) > 0:
                icr           = line.rfind('\r')
                line          = line if icr==-1 else line[icr+1:]
                output        += line
                self._current += line
        
        return output
            
    def reset(self):
        """ Reset object """
        self._current = ""
        
    def write(self, text, end='', flush=True):
        """
        Write to stdout using \r and \n translations.
        The 'end' and 'flush' parameters echo those of print()
        """
        text = self(text+end)
        print( text, end='', flush=flush )
        return self
