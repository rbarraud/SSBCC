reg       [7:0] T                       = 8'h00;

wire            conditional_true        = |T;

wire is_jump            = !opcode_curr[8] && opcode_curr[7];
wire do_jump            = is_jump && (!opcode_curr[6] || conditional_true);

wire R_pop              =

wire T_push             = opcode_curr[8] ||
wire T_pop              = do_jump ||
always @ (posedge i_clk)
  if (i_rst) begin
    T <= 8'h00;
  end else if (T_push) begin
    if (opcode_curr[8])
      T <= opcode_curr[7:0];
    else
      T <=
  end else if (T_pop) begin
    T <= N;
  end else begin
    T <= T;
  end

wire       math_adder_opcode = opcode_curr[0];
wire [7:0] math_adder_out;
always @ (T,N,math_adder_opcode)
  if (math_adder_opcode)
    math_adder_out <= N + T;
  else
    math_adder_out <= N - T;

wire [2:0] math_opcode  = opcode_curr[0+:3];
wire [7:0] math_out;
always @ (T,N,math_out)
  case (math_opcode)
     3'b000 : math_out <= T;                    // nop
     3'b001 : math_out <= {(8){!(|T)}};         // 0=
     3'b010 : math_out <= { T[0+:7], 1'b0 };    // 2*
     3'b011 : math_out <= { 1'b0, T[1+:7] };    // 2/
     3'b100 : math_out <= T & N;                // and
     3'b101 : math_out <= T | N;                // or
     3'b110 : math_out <= T ^ N;                // xor
     3'b111 : math_out <= N;                    // part of "over"
    default : math_out <= T;
  endcase

/*******************************************************************************
 *
 * Define the states for the bus muxes and then compute these stated from the
 * current opcode.
 *
 ******************************************************************************/

localparam C_BUS_PC_NORMAL      = 2'b00;
localparam C_BUS_PC_JUMP        = 2'b01;
localparam C_BUS_PC_RETURN      = 2'b11;

localparam C_BUS_P_NOP          = 2'b00;
localparam C_BUS_P_PC           = 2'b01;
localparam C_BUS_P_T            = 2'b10;

localparam C_BUS_T_PRE_OPCODE   = 3'b000;
localparam C_BUS_T_PRE_RETURN   = 3'b001;
localparam C_BUS_T_PRE_MEMORY   = 3'b010;
localparam C_BUS_T_PRE_N        = 3'b011;
localparam C_BUS_T_PRE_T        = 3'b100;
localparam C_BUS_T_PRE_INPORT   = 3'b101;

localparam C_BUS_T_NOP          = 2'b00;
localparam C_BUS_T_PRE          = 2'b01;
localparam C_BUS_T_MATH_DUAL    = 2'b10;
localparam C_BUS_T_MATH_SINGLE  = 2'b11;

localparam C_BUS_N_NOP          = 2'b00;
localparam C_BUS_N_T            = 2'b01;
localparam C_BUS_N_STACK        = 2'b10;

localparam C_STACK_NOP          = 2'b00;
localparam C_STACK_INC          = 2'b01;
localparam C_STACK_DEC          = 2'b10;

always @ (opcode_curr,T) begin
  s_bus_pc      <= C_BUS_PC_NORMAL;
  s_bus_t_pre   <= C_BUS_T_PRE_RETURN;
  s_bus_t       <= C_BUS_T_NOP;
  s_bus_n       <= C_BUS_N_NOP;
  s_stack       <= C_STACK_NOP;
  s_interrupt_enabled_next
                <= s_interrupt_enabled;
  s_interrupt_holdoff
                <= 1'b0;
  s_outport_next<= 1'b0;
  if (opcode_curr[8] == 1'b1) begin // push
    s_bus_t_pre <= C_BUS_T_PRE_OPCODE;
    s_bus_t     <= C_BUS_T_PRE;
    s_bus_n     <= C_BUS_N_T;
    s_stack     <= C_STACK_INC;
  end else if (opcode_curr[7] = 1'b1) begin // jump or jumpc
    if (opcode_curr[6] = 1'b0 || (|s_T))
      s_bus_pc  <= C_BUS_PC_JUMP;
    s_bus_t_pre <= C_BUS_T_PRE_N;
    s_bus_t     <= C_BUS_T_PRE;
    s_bus_n     <= C_BUS_N_STACK;
    s_stack     <= C_STACK_DEC;
    s_interrupt_holdoff <= 1'b1;
  end else case (opcode_curr[3+:4])
      4'b0000:  // nop
      4'bXXXX:  // drop, outport
                s_bus_t_pre     <= C_BUS_T_PRE_N;
                s_bus_t         <= C_BUS_T_PRE;
                s_bus_n         <= C_BUS_N_STACK;
                s_stack         <= C_STACK_DEC;
                s_outport_next  <= opcode_curr[0];
      4'bXXXX:  // dup
                s_bus_t_pre     <= C_BUS_T_PRE_T;
                s_bus_t         <= C_BUS_T_PRE;
                s_bus_n         <= C_BUS_N_T;
                s_stack         <= C_STACK_INC;
      4'bXXXX:  // swap
                s_bus_t_pre     <= C_BUS_T_PRE_N;
                s_bus_t         <= C_BUS_T_PRE;
                s_bus_n         <= C_BUS_N_T;
      4'bXXXX:  // @ (fetch)
                s_bus_t_pre     <= C_BUS_T_PRE_MEMORY;
                s_bus_t         <= C_BUS_T_PRE;
      4'bXXXX:  // inport
                s_bus_t_pre     <= C_BUS_T_PRE_INPORT;
                s_bus_t         <= C_BUS_T_PRE;
      4'bXXXX:  // dual-operand math:  add/sub/and/or/xor
                s_bus_t         <= C_BUS_T_MATH_DUAL;
                s_bus_n         <= C_BUS_N_STACK;
                s_stack         <= C_STACK_DEC;
      4'bXXXX:  // single-operand math: 0<, 2*, 2/
                s_bus_t         <= C_BUS_T_MATH_SINGLE;
      4'bXXXX:  // return
                s_bus_pc        <= C_BUS_PC_RETURN;
      4'bXXXX:  // >r (push top of data stack onto return stack and pop data stack)
      4'bXXXX:  // enable/disable the interrupt
                s_interrupt_enabled_next <= opcode_curr[0];
      4'bXXXX:  // call
      default:  // nop
    endcase
  end
end

/*******************************************************************************
 *
 * run the state machines for the processor components.
 *
 ******************************************************************************/

/*
 * Operate the program counter.
 */

// reduced-warning message method to extract the jump address from the top of
// the stack and the current opcode
wire s_PC_jump[C_RETURN_STACK_WIDTH-1:0];
generate
  if (C_RETURN_STACK_WIDTH <= 8) begin : gen_pc_narrow
    s_PC_jump <= s_T[0+:C_RETURN_STACK_WIDTH];
  end else begin : gen_pc_wide
    s_PC_jump <= { opcode_curr[0+:C_RETURN_STACK_WIDTH-8], s_T };
endgenerate

always @ (posedge i_clk)
  if (i_rst)
    s_PC <= C_RESET;
  else case (s_bus_pc)
    case C_BUS_PC_NORMAL: s_PC <= s_PC + 1;
    case C_BUS_PC_JUMP:   s_PC <= s_PC_jump;
    case C_BUS_PC_RETURN: s_PC <= s_R;
    default:              s_PC <= s_PC_next;
  endcase

wire [1:0] s_bus_t_pre
always @ (posedge s_registers_opcode)
  case (s_registers_opcode)
    4'b0000:            s_bus_t_pre <= C_BUS_T_PRE_RETURN;      // nop
    4'b0001:
    4'b0010:            s_bus_t_pre <= C_BUS_T_PRE_RETURN;      // add/sub
    4'b0011:            s_bus_t_pre <= C_BUS_T_PRE_RETURN;      // math_opcode
    default:            s_bus_t_pre <= C_BUS_T_PRE_RETURN;
  endcase;

always @ (opcode_curr[7+:2], s_registers_opcode) begin
  bus__adder_out <= 1'b0;
  bus__math_out  <= 1'b0;
  bus__latch_T   <= 1'b0;
  bus__pop_T     <= 1'b0;
  bus__push_T    <= 1'b0;
  bus__pop_N     <= 1'b0;
  bus__push_N    <= 1'b0;
  bus__pop_R     <= 1'b0;
  bus__push_R    <= 1'b0;
  if (opcode_curr[7+:2] == 2'b00)
    case (s_registers_opcode)
      4'b0000: ;                                // nop
      4'b0001: ?
      4'b0010: bus__adder_out     <= 1'b1;      // add/sub
               bus__latch_T       <= 1'b1;
               bus__pop_N         <= 1'b1;
      4'b0011: bus__math_out      <= 1'b1;      // math_opcode
               bus__latch_T       <= 1'b1;
               bus__pop_N         <= 1'b1;
      default:
    endcase
end

wire N_gets_top         = opcode_curr[8];
wire N_gets_third       = opcode_curr[7] || 
wire N_same