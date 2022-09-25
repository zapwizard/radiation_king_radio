#This code goes onto the Pi Pico
import board
import keypad
import digitalio
import neopixel
import pwmio
import analogio
from ulab import numpy as np

# Misc:
DISABLE_HEARTBEAT_LED = False # Note you won't be able to determine if the code is running without using a terminal

# Sweep: The movement of the dial at startup and during band changes.
SWEEP_DELAY = 0.003 # The speed at which the dial sweeps across the range

# Uart Related
UART_HEARTBEAT_INTERVAL = 3
PI_ZERO_HEARTBEAT_TIMEOUT = 30 # must be greater than the heartbeat interval on pi zero
UART_TIMEOUT = 0.1

#LED related:
led = digitalio.DigitalInOut(board.LED)
led.direction = digitalio.Direction.OUTPUT
LED_HEARTBEAT_INTERVAL = 1

#Pi Zero Reset switch
pi_zero_reset = digitalio.DigitalInOut(board.GP22)
pi_zero_reset.direction =  digitalio.Direction.OUTPUT
pi_zero_reset.value = True
pi_zero_soft_off = digitalio.DigitalInOut(board.GP2)
pi_zero_soft_off.direction =  digitalio.Direction.OUTPUT
pi_zero_soft_off.value = True


#Neopixel related
#Template: pixels[0] = (RED, GREEN, BLUE, WHITE) # 0-255
NEOPIXEL_SET_TIMEOUT = 1 # Amount of time a LED still stay on before resetting
NEOPIXEL_RANGE = 255 # Number of steps during fade on/off
NEOPIXEL_DIM_INTERVAL = 0.005

gauge_neopixel_order = neopixel.GRBW
GAUGE_PIXEL_QTY = 8
GAUGE_PIXEL_COLOR = (160, 32, 0, 38) # Use to alter the default color
GAUGE_PIXEL_MAX_BRIGHTNESS = 0.3 # Sets the entire strip max brightness
gauge_pixels = neopixel.NeoPixel(board.GP6, GAUGE_PIXEL_QTY, brightness=GAUGE_PIXEL_MAX_BRIGHTNESS, auto_write=True, pixel_order=gauge_neopixel_order)
gauge_pixels.fill((0, 0, 0, 0))
BRIGHTNESS_SMOOTHING = 0.1

aux_neopixel_order = neopixel.GRBW
AUX_PIXEL_QTY = 5
AUX_PIXEL_COLOR = (255, 20, 0, 0) # Use to alter the default color
AUX_PIXEL_MAX_BRIGHTNESS = 1 # Sets the entire strip max brightness
aux_pixels = neopixel.NeoPixel(board.GP7, AUX_PIXEL_QTY, brightness=AUX_PIXEL_MAX_BRIGHTNESS, auto_write=True, pixel_order=aux_neopixel_order)
aux_pixels.fill((0, 0, 0, 0))


# ADC related:
VOLUME_ADC_MIN = 1024 # Deliberately high to allow for self-calibration
VOLUME_ADC_MAX = 2048 # Deliberately low to allow for self-calibration
TUNING_ADC_MIN = 1024 # Deliberately high to allow for self-calibration
TUNING_ADC_MAX = 2048 # Deliberately low to allow for self-calibration
VOLUME_ADC = analogio.AnalogIn(board.A0) # I recommend using a switched "Audio" or logarithmic potentiometer for the volume control
TUNING_ADC = analogio.AnalogIn(board.A1)  # Use a switched linear potentiometer for the tuning control.
VOLUME_ADC_SMOOTHING = 0.6  # Float between 0 and 1. Lower means more smoothing, prevents lots of changes due to potentiometer noise, slows response
TUNING_ADC_SMOOTHING = 0.5  # Float between 0 and 1. Lower means more smoothing, prevents lots of changes due to potentiometer noise, slows response

# Float angle, angle has to change by more than this before the needle moves.
# Numbers great than 1 make for jumpy needle movement.
# Is overwritten when digital tuning to prevent ADC noise from changing the result.
TUNING_DEAD_ZONE = 0.3 # Angle
DIGITAL_TUNING_DEAD_ZONE = 5 # This is used if the station has been digitally tuned.

#Volume settings related to remote control
VOLUME_DEAD_ZONE = 0.05 # Float 0-1
DIGITAL_VOLUME_DEAD_ZONE = 0.1
DIGITAL_VOLUME_INCREMENT = 0.13

#Buttons:
buttons = keypad.Keys((board.GP9,board.GP10,board.GP11,board.GP12,board.GP13),value_when_pressed=False, pull=True, interval=0.05) # Reversed order during breadboard layout
#buttons = keypad.Keys((board.GP13,board.GP12,board.GP11,board.GP10,board.GP9),value_when_pressed=False, pull=True, interval=0.05)
BUTTON_QUANTITY = 5
BUTTON_SHORT_PRESS = 60 # in ms
BUTTON_LONG_PRESS = 2000 # in ms
BUTTON_PRESS_TIME = [None] * BUTTON_QUANTITY
BUTTON_RELEASE_TIME = [None] * BUTTON_QUANTITY
BUTTON_RELEASED = 0
BUTTON_PRESSED = 1
BUTTON_HELD = 2
button_state = [None] * BUTTON_QUANTITY
button_number = None
button_held_state= [False] * BUTTON_QUANTITY
button_event_type = None

#Switches:
switches = keypad.Keys((board.GP14,board.GP8),value_when_pressed=False, pull=True, interval=0.1)
SWITCH_QUANTITY = 2
SWITCH_CCW = False # Invert if your switch behavior seems backwards
SWITCH_CW = not SWITCH_CCW


#Motor controller related
PWM_FREQUENCY = 50000
SIN_PWM = pwmio.PWMOut(board.GP16, duty_cycle=0, frequency=PWM_FREQUENCY, variable_frequency=False)
SIN_POS = digitalio.DigitalInOut(board.GP18)
SIN_POS.direction = digitalio.Direction.OUTPUT
SIN_NEG = digitalio.DigitalInOut(board.GP17)
SIN_NEG.direction = digitalio.Direction.OUTPUT
COS_PWM = pwmio.PWMOut(board.GP21, duty_cycle=0, frequency=PWM_FREQUENCY, variable_frequency=False)
COS_POS = digitalio.DigitalInOut(board.GP19)
COS_POS.direction = digitalio.Direction.OUTPUT
COS_NEG = digitalio.DigitalInOut(board.GP20)
COS_NEG.direction = digitalio.Direction.OUTPUT
SIN_DIRECTION = False
COS_DIRECTION = False
motor_sin = None
motor_cos = None
motor_direction = None
PWM_MAX_VALUE = 65535 # 65535 max
MOTOR_REF_VOLTAGE = 3.3
MOTOR_ANGLE_MIN = 14 # This must match the settings on the Zero
MOTOR_ANGLE_MAX = 168
MOTOR_MID_POINT = (MOTOR_ANGLE_MAX - MOTOR_ANGLE_MIN) / 2 + 15
MOTOR_RANGE = MOTOR_ANGLE_MAX - MOTOR_ANGLE_MIN

# Ultrasonic Remote Related
REMOTE_ENABLED = True
REMOTE_CLK_PIN = board.GP3
REMOTE_DATA_PIN = board.GP4
REMOTE_SELECT_PIN = board.GP5
REMOTE_THRESHOLD = 200 # Minimum signal level needed to trigger a response
REMOTE_FREQ_MIN = 28000
REMOTE_FREQ_MAX = 41000
REMOTE_SAMPLE_FREQUENCY = 82000
REMOTE_SAMPLE_SIZE = 512  # the larger this number, the greater address separation, but slower processing time
REMOTE_SAMPLE_RATE = 0.4 # Float, Seconds
REMOTE_HALF_SAMPLE_SIZE = round(REMOTE_SAMPLE_SIZE/2)
REMOTE_TOLERANCE = 4 # How close to the address do we need to get


# Spectrogram address detected when pressing buttons on the remote
REMOTE_VALID = [
53,  # Channel Lower
77,  # Volume On/Off
72,  # Sound Mute
39 # Channel Higher
]

# This is used for the convolve code, but is slow.
FILTER = np.array([
    0.000000000000000000,
    0.000000406100845631,
    0.000013978139825631,
    -0.000051115492241930,
    0.000076113350543498,
    -0.000023994330458004,
    -0.000137455918358668,
    0.000338216472948484,
    -0.000401378579986739,
    0.000146917859771583,
    0.000434267221199771,
    -0.001060105600952861,
    0.001230308652123046,
    -0.000531183755838601,
    -0.000970850606243610,
    0.002533605283088154,
    -0.002995681462177029,
    0.001484750394143720,
    0.001783664957140502,
    -0.005197689894255255,
    0.006363971781333025,
    -0.003544571327827343,
    -0.002835511332234586,
    0.009679594645625685,
    -0.012423391546669648,
    0.007685397003450321,
    0.003997133923196201,
    -0.017183647308589983,
    0.023500151119012717,
    -0.016165642873769891,
    -0.005066757972168626,
    0.031488898001118974,
    -0.047615564223974789,
    0.037752980062440843,
    0.005823812974653906,
    -0.077236118170205273,
    0.157264364056455219,
    -0.220108806273868529,
    0.243901869341808908,
    -0.220108806273868529,
    0.157264364056455219,
    -0.077236118170205287,
    0.005823812974653906,
    0.037752980062440843,
    -0.047615564223974810,
    0.031488898001118974,
    -0.005066757972168628,
    -0.016165642873769891,
    0.023500151119012724,
    -0.017183647308589990,
    0.003997133923196201,
    0.007685397003450325,
    -0.012423391546669642,
    0.009679594645625688,
    -0.002835511332234587,
    -0.003544571327827342,
    0.006363971781333029,
    -0.005197689894255258,
    0.001783664957140502,
    0.001484750394143721,
    -0.002995681462177031,
    0.002533605283088155,
    -0.000970850606243612,
    -0.000531183755838600,
    0.001230308652123047,
    -0.001060105600952862,
    0.000434267221199771,
    0.000146917859771583,
    -0.000401378579986738,
    0.000338216472948484,
    -0.000137455918358669,
    -0.000023994330458004,
    0.000076113350543498,
    -0.000051115492241930,
    0.000013978139825631,
    0.000000406100845631,
    0.000000000000000000,
])

# Filter window https://fiiir.com/
# See the filter_generator.py file
# This is used instead of the convolve code and is faster

WINDOW = np.array([
-1.3877787807814457e-17,
1.3554576124077955e-05,
5.4227148311658535e-05,
0.00012204424012042525,
0.00021705003118953348,
0.00033930631782219667,
0.000488892457837356,
0.0006659052997262799,
0.0008704590961600006,
0.0011026854019042381,
0.0013627329562085205,
0.0016507675497451635,
0.001966971876186191,
0.002311545368513704,
0.0026847040201710415,
0.0030866801911709624,
0.003517722399287687,
0.0039780950964686534,
0.0044680784306112,
0.004987967992861164,
0.005538074550596392,
0.006118723766270859,
0.006730255902301821,
0.007373025512193654,
0.008047401118099193,
0.008753764875029754,
0.009492512221933258,
0.010264051519867867,
0.011068803677508565,
0.011907201764231302,
0.012779690611027274,
0.013686726399509581,
0.014628776239280404,
0.015606317733936448,
0.016619838535996106,
0.017669835891040937,
0.018756816171369962,
0.019881294399473184,
0.021043793761637,
0.022244845112000665,
0.02348498646739066,
0.024764762493264494,
0.026084723981102037,
0.027445427317589345,
0.028847433945943787,
0.030291309819735913,
0.031777624849568996,
0.033306952342980145,
0.034879868437934516,
0.03649695153028646,
0.03815878169558576,
0.03986594010561395,
0.041619008440034536,
0.04341856829355011,
0.04526520057895797,
0.04715948492650232,
0.04910199907992175,
0.05109331828959461,
0.0531340147031866,
0.05522465675420766,
0.05736580854888535,
0.059558029251766995,
0.061801872470460005,
0.06409788563992365,
0.06644660940672624,
0.06884857701368059,
0.07130431368527307,
0.07381433601430008,
0.07637915135012593,
0.07899925718897675,
0.08167514056668274,
0.08440727745428021,
0.087196132156887,
0.09004215671625726,
0.0929457903174255,
0.09590745869984538,
0.09892757357342631,
0.10200653203986923,
0.10514471601969971,
0.10834249168539434,
0.11160020890099179,
0.11491820066857764,
0.11829678258202886,
0.12173625228839707,
0.1252368889573094,
0.12879895275875852,
0.13242268434965027,
0.13610830436947086,
0.13985601294543296,
0.14366598920745233,
0.14753839081330197,
0.15147335348428612,
0.15547099055176739,
0.15953139251487933,
0.16365462660974361,
0.16784073639051061,
0.1720897413225313,
0.17640163638796388,
0.18077639170410917,
0.185213952154764,
0.18971423703487106,
0.19427713970874,
0.19890252728210267,
0.20359024028825923,
0.20834009238856527,
0.21315187008749698,
0.21802533246252906,
0.22296021090904578,
0.2279562089004996,
0.23301300176402318,
0.2381302364716897,
0.2433075314476083,
0.24854447639103294,
0.2538406321156504,
0.2591955304052077,
0.26460867388562637,
0.27007953591374245,
0.2756075604828017,
0.2811921621448284,
0.28683272594997616,
0.2925286074029612,
0.2982791324366648,
0.30408359740298385,
0.3099412690809989,
0.3158513847025152,
0.32181315199502536,
0.3278257492421301,
0.33388832536144375,
0.34,]+[
0.3461598636471636,
0.35236697776504233,
0.35862037493638427,
0.36491905902993327,
0.3712620053832075,
0.3776481610026512,
0.38407644478110464,
0.39054574773252193,
0.3970549332438593,
0.4036028373440446,
0.4101882689899279,
0.41681001036910414,
0.42346681721948776,
0.43015741916550904,
0.43688052007079137,
0.4436347984071612,
0.45041890763982684,
0.45723147662855945,
0.46407111004469437,
0.47093638880376354,
0.47782587051356035,
0.4847380899374274,
0.49167155947255,
0.49862476964302754,
0.5055961896074874,
0.5125842676809942,
0.519587431871003,
0.5266040904270911,
0.5336326324041984,
0.5406714282390974,
0.5477188303398014,
0.5547731736876211,
0.5618327764515586,
0.5688959406147335,
0.5759609526125166,
0.5830260839820495,
0.5900895920228136,
0.5971497204679086,
0.6042047001656924,
0.6112527497714307,
0.6182920764485936,
0.6253208765794342,
0.6323373364844761,
0.639339633150531,
0.646325934966866,
0.6532944024691261,
0.6602431890906241,
0.6671704419205939,
0.6740743024690076,
0.6809529074375451,
0.6878043894963082,
0.6946268780658598,
0.7014185001041708,
0.7081773808980523,
0.7149016448586436,
0.7215894163205325,
0.7282388203440716,
0.7348479835204595,
0.7414150347791486,
0.7479381061971443,
0.754415333809753,
0.7608448584223401,
0.7672248264226535,
0.7735533905932738,
0.7798287109237423,
0.786048955421927,
0.7922123009241798,
0.7983169339038444,
0.804361051277667,
0.8103428612096713,
0.8162605839120536,
0.8221124524426587,
0.8278967134985968,
0.8336116282055642,
0.8392554729024337,
0.8448265399206795,
0.8503231383582086,
0.8557435948471696,
0.8610862543153117,
0.8663494807404798,
0.8715316578978182,
0.876631190099276,
0.8816465029250011,
0.8865760439462159,
0.8914182834391762,
0.8961717150898135,
0.900834856688671,
0.9054062508157457,
0.9098844655148546,
0.9142680949571523,
0.918555760093427,
0.9227461092948133,
0.9268378189815633,
0.9308295942395268,
0.9347201694239943,
0.9385083087505672,
0.9421928068727251,
0.9457724894457662,
0.9492462136768063,
0.9526128688605293,
0.9558713769003891,
0.9590206928149699,
0.9620598052292236,
0.964987736850308,
0.9678035449277594,
0.9705063216977416,
0.973095194811123,
0.9755693277451404,
0.9779279201984213,
0.9801702084691397,
0.9822954658160963,
0.9843030028025181,
0.9861921676223873,
0.9879623464091123,
0.9896129635263722,
0.9911434818409672,
0.9925534029775251,
0.9938422675549184,
0.9950096554042603,
0.9960551857683569,
0.9969785174825043,
0.9977793491365277,
0.9984574192179714,
0.999012506236362,
0.99944442882847,
0.9997530458445159,
0.9999382564152686,
0.9999999999999999,
0.9999382564152686,
0.9997530458445159,
0.99944442882847,
0.999012506236362,
0.9984574192179714,
0.9977793491365277,
0.9969785174825043,
0.9960551857683569,
0.9950096554042603,
0.9938422675549184,
0.9925534029775251,
0.9911434818409672,
0.9896129635263722,
0.9879623464091123,
0.9861921676223873,
0.9843030028025181,
0.9822954658160963,
0.9801702084691397,
0.9779279201984213,
0.9755693277451404,
0.973095194811123,
0.9705063216977416,
0.9678035449277594,
0.964987736850308,
0.9620598052292236,
0.9590206928149699,
0.9558713769003891,
0.9526128688605293,
0.9492462136768063,
0.9457724894457662,
0.9421928068727251,
0.9385083087505672,
0.9347201694239943,
0.9308295942395268,
0.9268378189815633,
0.9227461092948133,
0.918555760093427,
0.9142680949571523,
0.9098844655148546,
0.9054062508157457,
0.900834856688671,
0.8961717150898135,
0.8914182834391762,
0.8865760439462159,
0.8816465029250011,
0.876631190099276,
0.8715316578978182,
0.8663494807404798,
0.8610862543153117,
0.8557435948471696,
0.8503231383582086,
0.8448265399206795,
0.8392554729024337,
0.8336116282055642,
0.8278967134985968,
0.8221124524426587,
0.8162605839120536,
0.8103428612096713,
0.804361051277667,
0.7983169339038444,
0.7922123009241798,
0.786048955421927,
0.7798287109237423,
0.7735533905932738,
0.7672248264226535,
0.7608448584223401,
0.754415333809753,
0.7479381061971443,
0.7414150347791486,
0.7348479835204595,
0.7282388203440716,
0.7215894163205325,
0.7149016448586436,
0.7081773808980523,
0.7014185001041708,
0.6946268780658598,
0.6878043894963082,
0.6809529074375451,
0.6740743024690076,
0.6671704419205939,
0.6602431890906241,
0.6532944024691261,
0.646325934966866,
0.639339633150531,
0.6323373364844761,
0.6253208765794342,
0.6182920764485936,
0.6112527497714307,
0.6042047001656924,
0.5971497204679086,
0.5900895920228136,
0.5830260839820495,
0.5759609526125166,
0.5688959406147335,
0.5618327764515586,
0.5547731736876211,
0.5477188303398014,
0.5406714282390974,
0.5336326324041984,
0.5266040904270911,
0.519587431871003,
0.5125842676809942,
0.5055961896074874,
0.49862476964302754,
0.49167155947255,
0.4847380899374274,
0.47782587051356035,
0.47093638880376354,
0.46407111004469437,
0.45723147662855945,
0.45041890763982684,
0.4436347984071612,
0.43688052007079137,
0.43015741916550904,
0.42346681721948776,
0.41681001036910414,
0.4101882689899279,
0.4036028373440446,
0.3970549332438593,
0.39054574773252193,
0.38407644478110464,
0.3776481610026512,
0.3712620053832075,
0.36491905902993327,
0.35862037493638427,
0.35236697776504233,
0.3461598636471636,
0.34,] + [
0.33388832536144375,
0.3278257492421301,
0.32181315199502536,
0.3158513847025152,
0.3099412690809989,
0.30408359740298385,
0.2982791324366648,
0.2925286074029612,
0.28683272594997616,
0.2811921621448284,
0.2756075604828017,
0.27007953591374245,
0.26460867388562637,
0.2591955304052077,
0.2538406321156504,
0.24854447639103294,
0.2433075314476083,
0.2381302364716897,
0.23301300176402318,
0.2279562089004996,
0.22296021090904578,
0.21802533246252906,
0.21315187008749698,
0.20834009238856527,
0.20359024028825923,
0.19890252728210267,
0.19427713970874,
0.18971423703487106,
0.185213952154764,
0.18077639170410917,
0.17640163638796388,
0.1720897413225313,
0.16784073639051061,
0.16365462660974361,
0.15953139251487933,
0.15547099055176739,
0.15147335348428612,
0.14753839081330197,
0.14366598920745233,
0.13985601294543296,
0.13610830436947086,
0.13242268434965027,
0.12879895275875852,
0.1252368889573094,
0.12173625228839707,
0.11829678258202886,
0.11491820066857764,
0.11160020890099179,
0.10834249168539434,
0.10514471601969971,
0.10200653203986923,
0.09892757357342631,
0.09590745869984538,
0.0929457903174255,
0.09004215671625726,
0.087196132156887,
0.08440727745428021,
0.08167514056668274,
0.07899925718897675,
0.07637915135012593,
0.07381433601430008,
0.07130431368527307,
0.06884857701368059,
0.06644660940672624,
0.06409788563992365,
0.061801872470460005,
0.059558029251766995,
0.05736580854888535,
0.05522465675420766,
0.0531340147031866,
0.05109331828959461,
0.04910199907992175,
0.04715948492650232,
0.04526520057895797,
0.04341856829355011,
0.041619008440034536,
0.03986594010561395,
0.03815878169558576,
0.03649695153028646,
0.034879868437934516,
0.033306952342980145,
0.031777624849568996,
0.030291309819735913,
0.028847433945943787,
0.027445427317589345,
0.026084723981102037,
0.024764762493264494,
0.02348498646739066,
0.022244845112000665,
0.021043793761637,
0.019881294399473184,
0.018756816171369962,
0.017669835891040937,
0.016619838535996106,
0.015606317733936448,
0.014628776239280404,
0.013686726399509581,
0.012779690611027274,
0.011907201764231302,
0.011068803677508565,
0.010264051519867867,
0.009492512221933258,
0.008753764875029754,
0.008047401118099193,
0.007373025512193654,
0.006730255902301821,
0.006118723766270859,
0.005538074550596392,
0.004987967992861164,
0.0044680784306112,
0.0039780950964686534,
0.003517722399287687,
0.0030866801911709624,
0.0026847040201710415,
0.002311545368513704,
0.001966971876186191,
0.0016507675497451635,
0.0013627329562085205,
0.0011026854019042381,
0.0008704590961600006,
0.0006659052997262799,
0.000488892457837356,
0.00033930631782219667,
0.00021705003118953348,
0.00012204424012042525,
5.4227148311658535e-05,
1.3554576124077955e-05,])
