################################################################################
#
# Copyright 2015, Sinclair R.F., Inc.
#
################################################################################

import math

from ssbccPeripheral import SSBCCperipheral
from ssbccUtil import CeilLog2
from ssbccUtil import SSBCCException

class servo_motor(SSBCCperipheral):
  """
  Servo Motor driver:\n
  Creates PWM modulated signals to operate micro servos for UAVs and similar.\n
  Usage:
    PERIPHERAL servo_motor      outport=O_name                          \\
                                {outsignal|outsignaln}=o_name           \\
                                freq_hz=FREQ_HZ                         \\
                                min_width=XXX{s|ms|us|ns}               \\
                                max_width=XXX{s|ms|us|ns}               \\
                                [default_width=XXX{s|ms|us|ns}]         \\
                                {period=XXX{s|ms|us|ns}|sync=o_name}    \\
                                [inperiod=I_name]                       \\
                                [scale=C_name]                          \\
                                [scale_max=C_name]\n
  Where:
    outport=O_name
      specifies the symbol used to write the 8-bit PWM control to this
      peripheral
      Note:  The name must start with "O_".
    {outsignal|outsignaln}=o_name
      specifies the name of the output PWM signal
      Note:  outsignal creates a positive pulse for the PWM control and
             outsignaln creates an inverted pulse for the PWM control.
      Note:  The name must start with "o_".
    freq_hz=FREQ_HZ
      specifies the processor clock speed to the peripheral
    min_width=XXX{s|ms|us|ns}
      specifies the minimum pulse width
      Note:  XXX may be an integer or a real number
      Note:  The minimum width must be a realizable positive value (since a
             pulse width of zero means no control is being given to the servo).
    max_width=XXX{s|ms|us|ns}
      specifies the maximum pulse width
      Note:  XXX may be an integer or a real number
    default_width=XXX{s|ms|us|ns}
      optionally specifies the default width of the PWM before it is set by the
      processor
      Note:  If the default width is not specified then the minimum width is
             used as the default width.
    {period=XXX{s|ms|us|ns}|sync=o_name}
      either specifies the rate at which the PWM is generated or synchronize the
      PWM generation to a preceding servo_motor peripheral with the output
      signal o_name
      Note:  XXX may be an integer or a real number
      Note:  When sync is specified the leading edges of the PWMs will coincide.
    inperiod=I_name
      optionally specifies an input port to receive the strobe generated by the
      associated period
      Note:  This optional parameter requires that period be specified.  It is
             not compatible with the sync parameter.
    scale=C_name
      optionally creates a constant named "C_name" which states how many clock
      cycles are used for each count in the 8-bit PWM control
      Note:  The name must start with "C_".
      Example:  A PWM range of 1000 to 1500 usec and a clock frequency of 8 MHz
                produces a value of ceil((1500-1000)*8/(256-1)) = 16 clock
                cycles per 8-bit control value count.
    scale_max=C_name
      optionally creates a constant named "C_name" wich states the upper limit
      of the continuous control range
      Note:  The name must start with "C_".
      Example:  For the example in "scale=C_name" the upper limit would be
                ceil((1500-1000)*8/16) = 250.  I.e., control values of 251
                through 255 inclusive will produce the same PWM width as the
                control value 250.
  Example:
    A micro servo that responds to positive PWM pulses between 1000 usec and
    1500 usec once every 20 msec and the processor clock is 8 MHz.  The
    architecture file would include the following:\n
      CONSTANT          C_FREQ_HZ       8_000_000
      PORTCOMMENT       servo motor control
      PERIPHERAL        servo_motor    outport=O_SERVO                  \\
                                       outsignal=o_servo                \\
                                       freq_hz=C_FREQ_HZ                \\
                                       min_width=1000us                 \\
                                       max_width=1500us                 \\
                                       period=20ms                      \\
                                       scale=C_servo_scale              \\
                                       scale_max=C_servo_scale_max\n
    will create a peripheral generating the desired PWM signal.\n
    The constants C_servo_scale and C_servo_scale_max could be reported by the
    micro controller to a controlling application to specify the sensitivity and
    upper limit for the servo motor controller.\n
  Example:
    Synchronize a second servo motor with PWM pulses between 1000 usec and 2500
    usec to the preceding servo motor controller:\n
      PERIPHERAL        servo_motor     outport=O_SERVO_2               \\
                                        outsignal=o_servo2              \\
                                        freq_hz=C_FREQ_HZ               \\
                                        min_width=1.0ms                 \\
                                        max_width=2.5ms                 \\
                                        sync=o_servo\n
  """

  def __init__(self,peripheralFile,config,param_list,loc):
    # Use the externally provided file name for the peripheral
    self.peripheralFile = peripheralFile;
    # Get the parameters.
    allowables = (
      ( 'default_width',        r'\S+',         lambda v : self.TimeMethod(config,v), ),
      ( 'freq_hz',              r'\S+$',        lambda v : self.IntMethod(config,v), ),
      ( 'inperiod',             r'I_\w+$',      None,   ),
      ( 'max_width',            r'\S+$',        lambda v : self.TimeMethod(config,v), ),
      ( 'min_width',            r'\S+$',        lambda v : self.TimeMethod(config,v), ),
      ( 'outport',              r'O_\w+$',      None,   ),
      ( 'outsignal',            r'o_\w+$',      None,   ),
      ( 'outsignaln',           r'o_\w+$',      None,   ),
      ( 'period',               r'\S+$',        lambda v : self.TimeMethod(config,v), ),
      ( 'scale',                r'C_\w+$',      None,   ),
      ( 'scale_max',            r'C_\w+$',      None,   ),
      ( 'sync',                 r'o_\w+$',      None,   ),
    )
    names = [a[0] for a in allowables];
    for param_tuple in param_list:
      param = param_tuple[0];
      if param not in names:
        raise SSBCCException('Unrecognized parameter "%s" at %s' % (param,loc,));
      param_test = allowables[names.index(param)];
      self.AddAttr(config,param,param_tuple[1],param_test[1],loc,param_test[2]);
    # Ensure the required parameters are provided.
    for paramname in (
      'outport',
      'freq_hz',
      'min_width',
      'max_width',
    ):
      if not hasattr(self,paramname):
        raise SSBCCException('Required parameter "%s" is missing at %s' % (paramname,loc,));
    # Ensure exactly one of mandatory exclusive pairs are specified.
    for exclusivepair in (
      ( 'outsignal',    'outsignaln',   ),
      ( 'period',       'sync',         ),
    ):
      if not hasattr(self,exclusivepair[0]) and not hasattr(self,exclusivepair[1]):
        raise SSBCCException('One of %s or %s must be specified at %s', (exclusivepair[0], exclusivepair[1], loc, ));
      if hasattr(self,exclusivepair[0]) and hasattr(self,exclusivepair[1]):
        raise SSBCCException('Only one of %s or %s may be specified at %s', (exclusivepair[0], exclusivepair[1], loc, ));
    # Set optional signals
    if not hasattr(self,'default_width'):
      self.default_width = self.min_width;
    # Ensure signal values are reasonable.
    if self.min_width >= self.max_width:
      raise SSBCCException('min_width must be smaller than max_width at %s' % loc);
    if not self.min_width <= self.default_width <= self.max_width:
      raise SSBCCException('default_width is not between min_width and max_width at %s' % loc);
    # Ensure the optionally provided "sync" servo_motor peripheral has been specified.
    if hasattr(self,'sync'):
      for p in config.peripheral:
        if (str(p.__class__) == str(self.__class__)) and (p.outsignal == self.sync):
          break;
      else:
        raise SSBCCException('Can\'t find preceding servo_motor peripheral with outsignal=%s at %s ' % (self.sync,loc,));
      if not hasattr(p,'period'):
        raise SSBCCException('servo_motor peripherial with outsignal=%s must have period specified to be used at %s' % (self.sync,loc,));
    # Translate the outsignal specification into a single member for the signal
    # name and a specification as to whether or not the signal is inverted.
    if hasattr(self,'outsignaln'):
      self.outsignal = self.outsignaln;
      self.invertOutsignal = True;
    else:
      self.invertOutsignal = False;
    # Set the string used to identify signals associated with this peripheral.
    self.namestring = self.outsignal;
    # Calculate the name of the signal to start the PWM.
    self.periodSignal = 's__%s__period_done' % (self.namestring if hasattr(self,'period') else self.sync)
    # Calculate the scaling and set the optionally specified constants.
    # TODO -- ensure the realizable min_width is positive
    self.scaleValue = int(math.ceil((self.max_width-self.min_width)*self.freq_hz/2**config.Get('data_width')));
    self.scale_maxValue = int(math.ceil((self.max_width-self.min_width)*self.freq_hz/self.scaleValue));
    for scalingPair in (
      ( 'scaling',      'scaleValue',           ),
      ( 'scale_max',    'scale_maxValue',       ),
    ):
      if hasattr(self,scalingPair[0]):
        config.AddConstant(scalingPair[1], getAttr(self,scalingPair[1]));
    # Add the I/O port, internal signals, and the INPORT and OUTPORT symbols for this peripheral.
    config.AddIO(self.outsignal,1,'output',loc);
    if hasattr(self,'period'):
      config.AddSignal(self.periodSignal, 1, loc);
    self.ix_outport = config.NOutports();
    config.AddOutport((self.outport,
                       False,
                       # empty list
                      ),loc);
    if hasattr(self,'inperiod'):
      config.AddSignal('s_SETRESET_%s' % self.periodSignal,1,loc);
      config.AddInport((self.inperiod,
                        (self.periodSignal, 1, 'set-reset',),
                       ),loc);

  def GenVerilog(self,fp,config):
    body = self.LoadCore(self.peripheralFile,'.v');
    if hasattr(self,'period'):
      body = re.sub(r'@PERIOD_BEGIN@\n','',body);
      body = re.sub(r'@PERIOD_END@\n','',body);
    else:
      body = re.sub(r'@PERIOD_BEGIN@.*?@PERIOD_END@\n','',body,flags=re.DOTALL);
    nbits_scale = CeilLog2(self.scaleValue);
    if nbits_scale == 0:
      body = re.sub(r'@SCALE_0_BEGIN@\n','',body);
      body = re.sub(r'@SCALE_0_ELSE@.*?@SCALE_0_END@\n','',body,flags=re.DOTALL);
    else:
      body = re.sub(r'@SCALE_0_BEGIN@.*?@SCALE_0_ELSE@\n','',body,flags=re.DOTALL);
      body = re.sub(r'@SCALE_0_END@\n','',body);
    scaled_min_width = int(math.floor(self.min_width*self.freq_hz/self.scaleValue));
    scaled_default_width = int(math.floor(self.default_width*self.freq_hz/self.scaleValue));
    scaled_max_width = int(math.floor(self.max_width*self.freq_hz/self.scaleValue));
    nbits_pwm = max(config.Get('data_width')+1,CeilLog2(scaled_max_width));
    pwm_formula = "%d'd%d + { %d'd0, s_N }" % (nbits_pwm,scaled_min_width-1,nbits_pwm-8,);
    if hasattr(self,'period'):
      period = self.period * self.freq_hz / self.scaleValue;
      nbits_period = CeilLog2(period);
    else:
      period = 1;
      nbits_period = 0;
    for subpair in (
      ( r'@DEFAULT_PWM@',       "%d'd%d" % (nbits_pwm,scaled_default_width-1,), ),
      ( r'@INVERT@',            '!' if self.invertOutsignal else '',            ),
      ( r'@IX_OUTPORT@',        "8'd%d" % self.ix_outport,                      ),
      ( r'@NAME@',              self.namestring,                                ),
      ( r'@NBITS_PERIOD@',      str(nbits_period),                              ),
      ( r'@NBITS_PWM@',         str(nbits_pwm),                                 ),
      ( r'@NBITS_SCALE@',       str(nbits_scale),                               ),
      ( r'@ONE_PERIOD@',        "%d'd1" % nbits_period,                         ),
      ( r'@ONE_PWM@',           "%d'd1" % nbits_pwm,                            ),
      ( r'@ONE_SCALE@',         "%d'd1" % nbits_scale,                          ),
      ( r'@OUTSIGNAL@',         self.outsignal,                                 ),
      ( r'@PERIOD_MINUS_ONE@',  "%d'd%d" % (nbits_period,period-1,),            ),
      ( r'@PWM_FORMULA@',       pwm_formula,                                    ),
      ( r'@SCALE_MINUS_ONE@',   "%d'd%d" % (nbits_scale,self.scaleValue-1,),    ),
      ( r'\bgen__',             'gen__%s__' % self.namestring,                  ),
      ( r'\bs__',               's__%s__' % self.namestring,                    ),
      ( r'@PERIOD_SIGNAL@',     self.periodSignal,                              ), # must be after ( r'\bs__', ...
    ):
      body = re.sub(subpair[0],subpair[1],body);
    body = self.GenVerilogFinal(config,body);
    fp.write(body);
