################################################################################
#
# Copyright 2012, Sinclair R.F., Inc.
#
################################################################################

from ssbccPeripheral import SSBCCperipheral
from ssbccUtil import SSBCCException;

class PWM_8bit(SSBCCperipheral):
   """Pulse Width Modulator (PWM) with 8-bit control.

This peripheral creates one or more PWMs.  The PWM is designed so that

Usage:
  PERIPHERAL PWM_8bit   outport=O_name \\
                        outsignal=o_name \\
                        ratemethod={clk/rate|count} \\
                        [invert|noinvert] \\
                        [instances=n]

Where:
  outport=O_name
    specifies the symbol used by the outport instruction to write a byte to the
    peripheral
    Note:  The name must start with "O_".
  outsignal=o_name
    specifies the name of the output signal
  ratemethod={clk/rate|count}
    specifies the frequency at which the PWM counter is incremented
    Example:  ratemethod=count means to increment the PWM counter once every
              "count" clock cycles.
  invert|noinvert
    optional configuration command to invert or to not invert the PWM output
    Default:  don't invert the output (i.e., a command of 0 means the output is
              always low)
    Note:  "invert" should be used when pulling the external signal to ground
           means the device is "on"
  instances=n
    specifies the number of PWMs for the peripheral
    Default:  The default is one PWM control and output.

The following OUTPORT is provided by this peripheral when instances=1:
  O_name
    output the next 8-bit value to transmit or to queue for transmission

The following OUTPORT is provided by this peripheral when instances=n is larger
than 1:
  O_name_0, O_name_1, ..., O_name_{n-1}
    If instances=n where n>1, then n outports are created
    Note:  O_name_i = ${O_name_0+i) where 0<=i<n.
    Note:  The PWM for o_name[i] is controlled by the outport O_name_i

Note:  The PWM counter is an 8-bit count that ranges from 1 to 255.  Each PWM
       output is '1' when this count is less than or equal to the commanded
       count.  The signal for a commanded count of 0 will never be on while the
       signal for a commanded count of 255 will always be on.

Example:  Control the intensity of an LED through a PWM.  The LED must flicker
          at a frequency greater than about 30 Hz in order for the flickering to
          not be visible by human eyes.  The LED is turned on when the signal to
          the LED is at ground.  The processor clock frequency is provided by
          the parameter G_CLK_FREQ_HZ.

  Within the processor architecture file include the configuration command:

  PERIPHERAL PWM_8bit   outport=O_PWM_LED \
                        outsignal=o_led \
                        ratemethod=G_CLK_FREQ_HZ/(30*255) \
                        invert

  Use the following assembly to set the LED to about 1/4 intensity:

  0x40 .outport(O_PWM_LED)

Example:  Similarly to obove, but for the three controls of a tri-color LED:

  Within the processor architecture file include the configuration command:

  PERIPHERAL PWM_8bit   outport=O_PWM_LED \
                        outsignal=o_led \
                        ratemethod=G_CLK_FREQ_HZ/(30*255) \
                        invert \
                        instances=3

  Use the following assembly to set the LEDs to 0x10 0x20 and 0x55:

  0x10 .outport(O_PWM_LED_0)
  0x20 .outport(O_PWM_LED_1)
  0x55 .outport(O_PWM_LED_2)

  or use the following function to send the three values on the stack where the
  top of the stack is 0x55 0x20 0x10 (this isn't less code, but it illustrates
  how to increment the outport index):

  ; ( u_pwm_led_2 u_pwm_led_1 u_pwm_led_0 - )
  .function set_led_pwms
  O_PWM_LED_0 ${3-1} :loop r> swap over outport drop 1+ r> .jumpc(loop,1-) drop
  .return(drop)
""";

  def __init__(self,config,param_list,ixLine):
    # Get the parameters.
    for param_tuple in param_list:
      param = param_tuple[0];
      param_arg = param_tuple[1];
      if param == 'outport':
        self.AddAttr(config,param,param_arg,r'O_\w+$',ixLine);
      elif param == 'outsignal':
        self.AddAttr(config,param,param_arg,r'o_\w+$',ixLine);
      elif param == 'ratemethod':
        self.ProcessRateMethod(config,param_arg,ixLine);
      elif param == 'invert':
        self.AddAttrNoArg(config,param,param_arg,ixLine);
      elif param == 'noinvert':
        self.AddAttrNoArg(config,param,param_arg,ixLine);
      elif param == 'instances':
        self.AddAttr(config,param,param_arg,r'[1-9]\d*$',ixLine);
        self.instances = int(self.instances);
      else:
        raise SSBCCException('Unrecognized parameter at line %d: %s' % (ixLine,param,));
    # Ensure the required parameters are provided.
    if not hasattr(self,'instances'):
      self.instances = 1;
    # Set optional parameters.
    if not hasattr(self,'invert') and not hasattr(self,'noinvert'):
      self.noinvert = True;
    # Ensure parameters do not conflict.
    if hasattr(self,'invert') and hasattr(self,'noinvert'):
      raise SSBCCException('Only one of "invert" or "noinvert" can be specified at line %d' % ixLine);
    # Use only one of mutually exclusive configuration settings.
    if hasattr(self,'noinvert'):
      self.invert = False;
    # Add the I/O port, internal signals, and the INPORT and OUTPORT symbols for this peripheral.
    self.AddIO(self.outsignal,self.instances,'output');
    if self.instances == 1:
      config.AddSignal('s__%s__tx' % self.outsignal, 8);
      config.AddOutport((self.outport,
                        ('s__%s__tx' % self.outsignal,8,'data',),
                        ('s__%s__wr' % self.outsignal,1,'strobe',),
                       ));
    else:
      for ixOutPort in range(self.instances):
        config.AddSignal('s__%s__%d__tx' % (self.outsignal,ixOutPort,) ,8);
        config.AddOutport((self.outport,
                          ('s__%s__%d__tx' % (self.outsignal,ixOutPort,),8,'data',),
                          ('s__%s__%d__wr' % (self.outsignal,ixOutPort,),1,'strobe',),
                         ));
    # Add the 'clog2' function to the core (if required).
    config.functions['clog2'] = True;

  def ProcessRateMethod(self,config,param_arg,ixLine):
    if hasattr(self,'ratemethod'):
      raise SSBCCException('ratemethod repeated at line %d' % ixLine);
    if param_arg.find('/') < 0:
      if self.IsInt(param_arg):
        self.ratemethod = str(self.ParseInt(param_arg));
      elif self.IsParameter(config,param_arg):
        self.ratemethod = param_arg;
      else:
        raise SSBCCException('ratemethod with no "/" must be an integer or a previously declared parameter at line %d' % ixLine);
    else:
      baudarg = re.findall('([^/]+)',param_arg);
      if len(baudarg) == 2:
        if not self.IsInt(baudarg[0]) and not self.IsParameter(config,baudarg[0]):
          raise SSBCCException('Numerator in ratemethod must be an integer or a previously declared parameter at line %d' % ixLine);
        if not self.IsInt(baudarg[1]) and not self.IsParameter(config,baudarg[1]):
          raise SSBCCException('Denominator in ratemethod must be an integer or a previously declared parameter at line %d' % ixLine);
        for ix in range(2):
          if self.IsInt(baudarg[ix]):
            baudarg[ix] = str(self.ParseInt(baudarg[ix]));
        self.ratemethod = '('+baudarg[0]+'+'+baudarg[1]+'/2)/'+baudarg[1];
    if not hasattr(self,'ratemethod'):
      raise SSBCCException('Bad ratemethod value at line %d:  "%s"' % (ixLine,param_arg,));

  def GenVerilog(self,fp,config):
    pass;
