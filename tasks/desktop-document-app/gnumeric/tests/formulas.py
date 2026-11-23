"""Independent function boundaries and context cases; no product implementation."""
from function_examples import EXAMPLES


def cases():
    out=[];seen=set()
    def add(family,formula,meaning='',error=False):
        formula='='+formula.lstrip('=')
        if formula.casefold() in seen:return
        seen.add(formula.casefold())
        out.append({'family':family,'formula':formula,'meaning':meaning or formula,'error':bool(error)})
    for family,expr in EXAMPLES:
        add('functions-'+family,expr,'Documented function example '+expr)
    # Distinct sign, rounding, coercion, vector and domain boundaries.
    unary={
      'ABS':['-2.75','0','3.25'], 'SIGN':['-7','0','4'], 'INT':['-2.25','2.75','0'],
      'TRUNC':['-2.75','3.25'], 'EVEN':['-3.1','0','4.1'], 'ODD':['-2.1','0','3.1'],
      'SQRT':['0','2','81'], 'SQRTPI':['0','2.5'], 'EXP':['-2','0','2'],
      'LN':['0.125','1','8'], 'LOG10':['0.01','1000'], 'LOG2':['0.25','32'],
      'SIN':['-1.25','0','PI()/2'], 'COS':['-1.25','0','PI()'], 'TAN':['-0.75','0','0.75'],
      'ASIN':['-1','0.25','1'], 'ACOS':['-1','0.25','1'], 'ATAN':['-4','0','4'],
      'SINH':['-2','0','2'], 'COSH':['-2','0','2'], 'TANH':['-2','0','2'],
      'ASINH':['-2','0','2'], 'ACOSH':['1','2'], 'ATANH':['-0.75','0','0.75'],
      'COT':['0.75','-0.75'], 'SEC':['0','0.75'], 'CSC':['0.75','-0.75'],
      'ACOT':['0','2'], 'ACOTH':['-2','2'], 'COTH':['-2','2'], 'SECH':['-2','2'],
      'CSCH':['-2','2'], 'ASEC':['-2','2'], 'ACSC':['-2','2'], 'ASECH':['0.25','1'],
      'ACsch':['-2','2'], 'DEGREES':['PI()/4','-PI()'], 'RADIANS':['45','-180'],
      'FACT':['0','7'], 'FACTDOUBLE':['0','8','9'], 'GAMMA':['0.5','4.5'],
      'GAMMALN':['0.5','4.5'], 'ERF':['-1','0.5','2'], 'ERFC':['-1','0.5','2'],
      'PHI':['0','1.5','-1.5'], 'GAUSS':['0','1.5','-1.5'],
      'ISEVEN':['-2.5','-3','0'], 'ISODD':['-2.5','-3','0'],
    }
    for fn,args in unary.items():
        for a in args:add('numeric-boundaries',f'{fn}({a})',f'{fn} at {a}')
    for fn in ['ROUND','ROUNDUP','ROUNDDOWN','TRUNC']:
        for a,n in [('-12.55',1),('12.55',1),('149',-2),('-149',-2),('0.00495',3)]:
            add('rounding',f'{fn}({a},{n})',f'{fn}: sign and digit-place boundary')
    for fn in ['FLOOR','CEILING','MROUND']:
        for a,b in [('8.7','2.5'),('-8.7','-2.5'),('0','2.5')]:add('rounding',f'{fn}({a},{b})')
    for a,b in [(17,5),(-17,5),(17,-5),(-17,-5),(0,5)]:
        for fn in ('MOD','QUOTIENT'):add('arithmetic',f'{fn}({a},{b})')
    for formula in ['2+3*4','(2+3)*4','-2^2','(-2)^2','2^3^2','50%*8',
                    '2^(-3)','1/8','10-3-2','(10-3)-2','10-(3-2)',
                    '2=2','2<>3','2<3','3<=3','4>3','4>=5',
                    '"a"&"b"','"12"+3','TRUE+2','FALSE*9','1=TRUE',
                    'SUM(2,"3",TRUE)','SUM(Data!A1:A7)','PRODUCT(Data!A1:A5)',
                    'SUMSQ(Data!A1:A7)','SUMPRODUCT(Data!A1:A5,Data!B1:B5)',
                    'SERIESSUM(2,1,2,{1;2;3})','SUMX2MY2(Data!A1:A5,Data!B1:B5)',
                    'SUMX2PY2(Data!A1:A5,Data!B1:B5)','SUMXMY2(Data!A1:A5,Data!B1:B5)',
                    'GCD(18,24,42)','LCM(4,6,10)','MULTINOMIAL(2,3,4)',
                    'COMBIN(8,3)','COMBINA(5,3)','PERMUT(8,3)','PERMUTATIONA(5,3)',
                    'POWER(9,0.5)','POWER(2,-4)','ATAN2(-3,4)','ATAN2(3,-4)',
                    'LOG(81,3)','LOG(0.125,2)','DELTA(3,3)','DELTA(3,4)',
                    'GESTEP(3,2)','GESTEP(2,3)','ROMAN(1999)','ARABIC("MCMXCIX")']:
        add('arithmetic',formula)
    # Scalar and mixed-type aggregate rules, rank/tie policies, interpolation.
    aggregates=['SUM','PRODUCT','AVERAGE','AVERAGEA','COUNT','COUNTA','COUNTBLANK','MAX','MIN',
                'MAXA','MINA','MEDIAN','GEOMEAN','HARMEAN','DEVSQ','AVEDEV','STDEV','STDEVP',
                'STDEVA','STDEVPA','VAR','VARP','VARA','VARPA','SKEW','SKEWP','KURT','KURTP']
    for fn in aggregates:
        for range_ in ['Data!A1:A5','Data!D1:D5']:
            # GEOMEAN/HARMEAN and high-order moments need enough numeric observations.
            if range_.startswith('Data!D') and fn in ('GEOMEAN','HARMEAN','SKEW','SKEWP','KURT','KURTP','STDEV','VAR'):continue
            add('aggregates',f'{fn}({range_})')
    for fn in ['LARGE','SMALL']:
        for k in [1,3,5]:add('order-statistics',f'{fn}(Data!A1:A5,{k})')
    for fn in ['PERCENTILE','PERCENTILE.INC','PERCENTILE.EXC']:
        for q in [.25,.5,.75]:add('order-statistics',f'{fn}(Data!A1:A5,{q})')
    for fn in ['QUARTILE','QUARTILE.INC','QUARTILE.EXC']:
        for q in [1,2,3]:add('order-statistics',f'{fn}(Data!A1:A5,{q})')
    for fn in ['RANK','RANK.EQ','RANK.AVG']:
        for order in [0,1]:add('order-statistics',f'{fn}(4,{{1;4;4;9;12}},{order})')
    for fn in ['PERCENTRANK','PERCENTRANK.INC','PERCENTRANK.EXC']:
        for v in [2,6,8]:add('order-statistics',f'{fn}(Data!A1:A5,{v},4)')
    for fn in ['CORREL','COVAR','COVARIANCE.P','COVARIANCE.S','PEARSON','RSQ','SLOPE','INTERCEPT','STEYX']:
        add('regression',f'{fn}(Data!B1:B5,Data!A1:A5)')
    for formula in ['FORECAST(10,Data!B1:B5,Data!A1:A5)', 'TRIMMEAN({1;2;3;5;7;100},1/3)',
                    'MODE({2;3;2;5;3;3})','STANDARDIZE(7,5,2)','FISHER(0.5)','FISHERINV(0.75)',
                    'ZTEST(Data!A1:A5,7,4)','TTEST(Data!A1:A5,Data!B1:B5,2,1)',
                    'TTEST(Data!A1:A5,Data!B1:B5,1,2)','TTEST(Data!A1:A5,Data!B1:B5,2,3)',
                    'FTEST(Data!A1:A5,Data!B1:B5)','CHITEST({10,20;30,40},{12,18;28,42})']:
        add('statistical-tests',formula)
    # Distribution modes, tails and inverses use meaningful parameter changes.
    distributions={
      'NORMDIST':[('2,1,3,FALSE','2,1,3,TRUE')],
      'NORM.DIST':[('2,1,3,FALSE','2,1,3,TRUE')],
      'LOGNORMDIST':[('2,0.5,1','0.5,0.5,1')],
      'LOGNORM.DIST':[('2,0.5,1,FALSE','2,0.5,1,TRUE')],
      'EXPONDIST':[('1.5,2,FALSE','1.5,2,TRUE')],
      'WEIBULL':[('2,3,4,FALSE','2,3,4,TRUE')],
      'GAMMADIST':[('2,3,4,FALSE','2,3,4,TRUE')],
      'GAMMA.DIST':[('2,3,4,FALSE','2,3,4,TRUE')],
      'BINOMDIST':[('3,8,0.4,FALSE','3,8,0.4,TRUE')],
      'BINOM.DIST':[('3,8,0.4,FALSE','3,8,0.4,TRUE')],
      'NEGBINOMDIST':[('3,5,0.4','0,5,0.4')],
      'POISSON':[('3,2,FALSE','3,2,TRUE')],
      'POISSON.DIST':[('3,2,FALSE','3,2,TRUE')],
      'HYPGEOMDIST':[('2,5,8,20','3,5,8,20')],
      'BETADIST':[('0.3,2,4','0.7,2,4')],
      'TDIST':[('1.5,8,1','1.5,8,2')],
      'CHIDIST':[('3,4','6,4')], 'FDIST':[('2,4,8','0.5,4,8')],
      'NORMINV':[('0.1,2,3','0.9,2,3')], 'NORMSINV':[('0.1','0.9')],
      'LOGINV':[('0.2,0.5,1','0.8,0.5,1')], 'GAMMAINV':[('0.2,3,4','0.8,3,4')],
      'BETAINV':[('0.2,2,4','0.8,2,4')], 'TINV':[('0.05,8','0.5,8')],
      'CHIINV':[('0.05,4','0.5,4')], 'FINV':[('0.05,4,8','0.5,4,8')],
      'CRITBINOM':[('10,0.3,0.1','10,0.3,0.9')],
      'CONFIDENCE':[('0.05,2,25','0.1,2,25')],
      'CONFIDENCE.T':[('0.05,2,25','0.1,2,25')],
    }
    for fn,pairs in distributions.items():
        for pair in pairs:
            for args in pair:add('distributions',f'{fn}({args})')
    r_specs={'NORM':'0.5,1,2','BETA':'0.3,2,4','BINOM':'3,8,0.4','CAUCHY':'0.5,0,2',
             'CHISQ':'3,4','EXP':'1.5,2','F':'2,4,8','GAMMA':'2,3,4',
             'GEOM':'3,0.4','HYPER':'2,8,12,5','LNORM':'2,0.5,1',
             'LOGIS':'0.5,0,2','NBINOM':'3,5,0.4','POIS':'3,2','T':'1.5,8',
             'UNIF':'0.3,0,1','WEIBULL':'2,3,4'}
    for dist,args in r_specs.items():
        for logarithm in ['FALSE','TRUE']:add('r-distributions',f'R.D{dist}({args},{logarithm})')
        for tail in ['FALSE','TRUE']:
            add('r-distributions',f'R.P{dist}({args},{tail},FALSE)')
    # Context-sensitive logical evaluation, error propagation and coercion.
    for formula in ['IF(TRUE,12,1/0)','IF(FALSE,1/0,17)','IF(0,"yes","no")','IF(2,"yes","no")',
                    'IFERROR(1/0,"fallback")','IFERROR(12,"fallback")','IFNA(NA(),42)','IFNA(7,42)',
                    'AND(TRUE,1,Data!A1:A5)','AND(TRUE,FALSE)','OR(FALSE,0,2)','OR(FALSE,0)',
                    'XOR(TRUE,FALSE,TRUE)','XOR(TRUE,FALSE,FALSE)','NOT(0)','NOT(3)',
                    'SWITCH(2,1,"one",2,"two","other")','SWITCH(4,1,"one",2,"two","other")',
                    'IFS(FALSE,2,TRUE,7)','CHOOSE(3,12,24,36)', 'TRUE()', 'FALSE()',
                    'N("text")','N(TRUE)','N(12.5)','T(15)','T("text")',
                    'ISNUMBER(12)','ISNUMBER("12")','ISTEXT("12")','ISTEXT(12)',
                    'ISLOGICAL(TRUE)','ISLOGICAL(1)','ISBLANK(Data!D5)','ISBLANK(Data!D4)',
                    'ISREF(Data!A1)','ISREF(12)','TYPE(12)','TYPE("text")','TYPE(TRUE)','TYPE(NA())',
                    'ISFORMULA(Data!D4)','ISNONTEXT(Data!D4)','ISNONTEXT(Data!C1)']:
        add('logical-types',formula)
    for code in ['#DIV/0!','#VALUE!','#REF!','#NAME?','#NUM!','#N/A','#NULL!']:
        for fn in ['ISERROR','ISERR','ISNA','ERROR.TYPE']:
            add('error-classification',f'{fn}(ERROR("{code}"))')
    # Text: Unicode, optional arguments, occurrence selection and exact/wildcard matching.
    texts={
      'LEN':['"café 東京"','""'], 'LENB':['"café"','"abc"'],
      'LEFT':['"spreadsheet",6','"東京abc",2','"abc",0'],
      'RIGHT':['"spreadsheet",5','"東京abc",2','"abc",0'],
      'MID':['"spreadsheet",3,4','"abc",20,3','"café東京",4,2'],
      'LOWER':['"AbC ÉTÉ"'], 'UPPER':['"AbC été"'], 'PROPER':['"sMALL tOWN"'],
      'TRIM':['"  one   two  "'], 'CLEAN':['CHAR(9)&"x"&CHAR(10)'],
      'FIND':['"a","banana",3','"na","banana"'],
      'SEARCH':['"B?N*","banana"','"~*","a*b"'],
      'SUBSTITUTE':['"one one one","one","X"','"one one one","one","X",2'],
      'REPLACE':['"abcdefgh",3,4,"XYZ"','"abc",2,0,"X"'],
      'REPT':['"ab",3','"x",0'], 'EXACT':['"Abc","abc"','"été","été"'],
      'CONCATENATE':['"a",12,TRUE'], 'CONCAT':['Data!C1:C3'],
      'TEXTJOIN':['" / ",TRUE,Data!D3:D5','" / ",FALSE,Data!D3:D5'],
      'CHAR':['65','233'], 'CODE':['"A"','"é"'], 'UNICHAR':['26481'], 'UNICODE':['"東"'],
      'VALUE':['"1,234.5"','"12.5%"'], 'NUMBERVALUE':['"1.234,5",",","."'],
      'TEXT':['1234.5,"#,##0.00"','0.125,"0.0%"','DATE(2024,2,29),"yyyy-mm-dd"'],
      'FIXED':['1234.567,2,TRUE','1234.567,1,FALSE'], 'DOLLAR':['1234.567,2','-12.34,0'],
      'REGEXTEST':['"ab123cd","[0-9]+"','"abc","[0-9]+"'],
      'REGEXEXTRACT':['"abc-123-xyz","[0-9]+"'],
      'REGEXREPLACE':['"a12b34","[0-9]+","X"'],
      'BAHTTEXT':['21.25'], 'ASC':['"ABC xyz 123"'],
    }
    for fn, args in texts.items():
        for a in args:add('text',f'{fn}({a})')
    # Date systems, leap boundaries, optional bases and international weekends.
    for y,m,d in [(2024,2,29),(2023,2,29),(2024,13,1),(2024,0,1),(2024,3,0),(99,12,31),(1900,3,1)]:
        add('dates',f'DATE({y},{m},{d})')
    for fn in ['YEAR','MONTH','DAY','WEEKNUM','ISOWEEKNUM','WEEKDAY','MONTH','DAY']:
        for date in ['DATE(2024,2,29)','DATE(2024,12,31)']:add('dates',f'{fn}({date})')
    for mode in [1,2,3,11,12,13,14,15,16,17]:add('dates',f'WEEKDAY(DATE(2024,1,7),{mode})')
    for mode in [1,2,11,12,13,14,15,16,17,21]:add('dates',f'WEEKNUM(DATE(2024,12,31),{mode})')
    for fn in ['EDATE','EOMONTH']:
        for n in [-13,-1,0,1,13]:add('dates',f'{fn}(DATE(2024,1,31),{n})')
    for base in range(5):
        add('dates',f'YEARFRAC(DATE(2023,12,15),DATE(2024,3,15),{base})')
    for unit in ['"y"','"m"','"d"','"md"','"ym"','"yd"']:
        add('dates',f'DATEDIF(DATE(2020,2,28),DATE(2024,3,15),{unit})')
    for formula in ['DATEVALUE("2024-02-29")','TIME(25,90,30)','TIME(0,0,0)','TIMEVALUE("13:45:30")',
                    'HOUR(TIME(13,45,30))','MINUTE(TIME(13,45,30))','SECOND(TIME(13,45,30))',
                    'DAYS(DATE(2024,3,1),DATE(2024,2,28))','DAYS360(DATE(2024,2,29),DATE(2024,3,31),FALSE)',
                    'DAYS360(DATE(2024,2,29),DATE(2024,3,31),TRUE)',
                    'NETWORKDAYS(DATE(2024,1,1),DATE(2024,1,14))',
                    'NETWORKDAYS(DATE(2024,1,1),DATE(2024,1,14),{45292;45293})',
                    'WORKDAY(DATE(2024,1,5),3)','WORKDAY(DATE(2024,1,8),-3)',
                    'UNIX2DATE(1709251200)','DATE2UNIX(DATE(2024,3,1))',
                    'EASTERSUNDAY(2024)','ISLEAPYEAR(2024)','ISLEAPYEAR(2100)']:
        add('dates',formula)
    for weekend in ['1','2','7','11','17','"0000011"','"1000001"']:
        add('dates',f'NETWORKDAYS.INTL(DATE(2024,1,1),DATE(2024,1,14),{weekend})')
        add('dates',f'WORKDAY.INTL(DATE(2024,1,5),5,{weekend})')
    # References and matching: positional, approximate, wildcard, case-insensitive, missing.
    for formula in ['ADDRESS(5,3,1)','ADDRESS(5,3,2)','ADDRESS(5,3,3)','ADDRESS(5,3,4)',
                    'ADDRESS(5,3,1,FALSE,"Data")','ROW(Data!A7)','COLUMN(Data!G1)',
                    'ROWS(Data!A1:C7)','COLUMNS(Data!A1:C7)',
                    'INDEX(Data!A1:B5,3,2)','INDEX(Data!C1:C5,4)',
                    'MATCH(4,Data!A1:A5,0)','MATCH(6,Data!A1:A5,1)',
                    'MATCH(6,{16;8;4;2;1},-1)','MATCH("a*",Data!C1:C5,0)',
                    'VLOOKUP(4,Data!A1:B5,2,FALSE)','VLOOKUP(6,Data!A1:B5,2,TRUE)',
                    'HLOOKUP(20,Data!E1:G2,2,FALSE)','HLOOKUP(25,Data!E1:G2,2,TRUE)',
                    'LOOKUP(6,Data!A1:A5,Data!B1:B5)',
                    'INDIRECT("Data!A4")','SUM(OFFSET(Data!A1,1,0,3,1))',
                    'SUMIF(Data!C1:C5,"a*",Data!A1:A5)',
                    'SUMIF(Data!A1:A5,">3",Data!B1:B5)',
                    'COUNTIF(Data!C1:C5,"apple")','COUNTIF(Data!C1:C5,"a*")',
                    'COUNTIF(Data!A1:A7,">=0")','COUNTIFS(Data!A1:A5,">2",Data!B1:B5,"<20")',
                    'SUMIFS(Data!B1:B5,Data!A1:A5,">2",Data!A1:A5,"<10")',
                    'AVERAGEIF(Data!A1:A5,">2",Data!B1:B5)',
                    'AVERAGEIFS(Data!B1:B5,Data!A1:A5,">2",Data!A1:A5,"<10")',
                    'SUBTOTAL(9,Data!A1:A7)','SUBTOTAL(1,Data!A1:A7)',
                    'SUM(TRANSPOSE({1,2;3,4}))','MDETERM({1,2;3,5})',
                    'SUM(MMULT({1,2;3,4},{2,0;1,2}))','SUM(MINVERSE({1,2;3,5}))']:
        add('lookup-arrays',formula)
    for fn in ['DSUM','DPRODUCT','DAVERAGE','DMAX','DMIN','DCOUNT','DCOUNTA','DSTDEV','DSTDEVP','DVAR','DVARP']:
        for criteria in ['Database!F1:F2','Database!F1:G2']:
            add('database',f'{fn}(Database!A1:D7,"Yield",{criteria})')
    add('database','DGET(Database!A1:D7,"Yield",Database!F1:G2)')
    # Engineering conversions preserve sign and padding as well as scale/offset.
    conversions=[('m','ft'),('ft','m'),('km','mi'),('kg','lbm'),('lbm','g'),('l','gal'),('gal','l'),
                 ('C','F'),('F','C'),('C','K'),('K','C'),('Pa','atm'),('atm','Pa'),('N','dyn'),
                 ('J','cal'),('Wh','J'),('W','HP'),('hr','sec'),('day','hr'),('m/sec','km/hr'),
                 ('byte','bit'),('kbyte','byte'),('m^2','ft^2'),('m^3','l')]
    for a,b in conversions:add('engineering',f'CONVERT(12.5,"{a}","{b}")')
    for fn,value in [('BIN2DEC','"1111111111"'),('OCT2DEC','"7777777777"'),('HEX2DEC','"FFFFFFFFFF"'),
                     ('DEC2BIN','-1'),('DEC2OCT','-1'),('DEC2HEX','-1'),
                     ('BIN2HEX','"101101"'),('HEX2BIN','"2D"'),('OCT2HEX','"55"'),('HEX2OCT','"2D"'),
                     ('BIN2OCT','"101101"'),('OCT2BIN','"55"')]:add('engineering',f'{fn}({value})')
    for fn in ['DEC2BIN','DEC2OCT','DEC2HEX']:add('engineering',f'{fn}(19,8)')
    for fn in ['BITAND','BITOR','BITXOR']:add('engineering',f'{fn}(13,11)')
    for fn in ['BITLSHIFT','BITRSHIFT']:
        for n in [-2,2]:add('engineering',f'{fn}(44,{n})')
    for fn in ['BESSELI','BESSELJ','BESSELK','BESSELY']:
        for n in [0,2]:add('engineering',f'{fn}(1.5,{n})')
    for fn in ['IMABS','IMREAL','IMAGINARY','IMARGUMENT','IMCONJUGATE','IMEXP','IMLN','IMLOG10','IMLOG2','IMSQRT',
               'IMSIN','IMCOS','IMTAN','IMCOT','IMSEC','IMCSC','IMSINH','IMCOSH','IMTANH','IMCOTH','IMSECH','IMCSCH']:
        for z in ['"2+3i"','"-1-2j"']:add('complex',f'{fn}({z})')
    for fn in ['IMSUM','IMSUB','IMPRODUCT','IMDIV']:add('complex',f'{fn}("2+3i","1-2i")')
    for n in [-2,.5,3]:add('complex',f'IMPOWER("2+3i",{n})')
    # Financial signs, payment timing, depreciation methods, day-count bases.
    for timing in [0,1]:
        for fn,args in {'FV':'0.04,5,-100,1000','PV':'0.04,5,-100,1000','PMT':'0.04,5,1000,100',
                        'NPER':'0.04,-100,1000,0','RATE':'12,-100,1000,0'}.items():
            add('financial',f'{fn}({args},{timing})')
        for fn in ['IPMT','PPMT']:
            for period in [1,6,12]:add('financial',f'{fn}(0.05/12,{period},12,1000,0,{timing})')
        for fn in ['CUMIPMT','CUMPRINC']:add('financial',f'{fn}(0.05/12,12,1000,1,6,{timing})')
    for formula in ['NPV(0.1,100,200,300)-400','IRR({-1000;200;300;600})',
                    'MIRR({-1000;200;300;600},0.1,0.12)', 'XNPV(0.1,{-1000;400;700},{43831;44197;44562})',
                    'XIRR({-1000;400;700},{43831;44197;44562})',
                    'FVSCHEDULE(100,{0.03;0.04;0.05})','EFFECT(0.06,12)','NOMINAL(0.0616778118645,12)',
                    'SLN(1000,100,5)','SYD(1000,100,5,2)','DB(1000,100,5,2)',
                    'DDB(1000,100,5,2)','DDB(1000,100,5,2,1.5)','VDB(1000,100,5,1,3)',
                    'DOLLARDE(1.02,16)','DOLLARFR(1.125,16)','PDURATION(0.1,100,200)',
                    'RRI(5,100,200)','ISPMT(0.05,2,5,1000)','TBILLPRICE(DATE(2024,1,1),DATE(2024,6,1),0.04)',
                    'TBILLYIELD(DATE(2024,1,1),DATE(2024,6,1),98)','TBILLEQ(DATE(2024,1,1),DATE(2024,6,1),0.04)']:
        add('financial',formula)
    for base in range(5):
        for fn,args in {'PRICE':'0.04,0.05,100,2','YIELD':'0.04,97.5,100,2',
                        'DURATION':'0.04,0.05,2','MDURATION':'0.04,0.05,2',
                        'DISC':'97.5,100','INTRATE':'97.5,100','PRICEDISC':'0.04,100',
                        'YIELDDISC':'97.5,100','RECEIVED':'100,0.04',
                        'COUPDAYBS':'2','COUPDAYS':'2','COUPDAYSNC':'2','COUPNCD':'2','COUPNUM':'2','COUPPCD':'2'}.items():
            add('financial-basis',f'{fn}(DATE(2024,3,15),DATE(2027,9,30),{args},{base})')
    # Explicit invalid-domain and error paths; never accepted accidentally as a valid result.
    errors=['1/0','SQRT(-1)','LN(0)','LOG(-2,10)','LOG(3,1)','ASIN(2)','ACOS(-2)','ACOSH(0.5)','ATANH(1)',
            'FACT(-1)','COMBIN(3,4)','PERMUT(3,4)','MOD(3,0)','QUOTIENT(3,0)','GAMMA(-2)',
            'AVERAGE(Data!D5)','GEOMEAN({1;-2;3})','HARMEAN({1;0;3})','STDEV({2})','VAR({2})',
            'LARGE(Data!A1:A5,0)','SMALL(Data!A1:A5,6)','PERCENTILE(Data!A1:A5,1.2)',
            'MATCH(3,Data!A1:A5,0)','VLOOKUP(3,Data!A1:B5,2,FALSE)','VLOOKUP(2,Data!A1:B5,3,FALSE)',
            'INDEX(Data!A1:B5,7,1)','INDIRECT("not_a_cell")','CHOOSE(0,1,2)','CHOOSE(3,1,2)',
            'LEFT("abc",-1)','RIGHT("abc",-1)','MID("abc",0,2)','FIND("z","abc")','SEARCH("z","abc")',
            'REPT("x",-1)','VALUE("not a number")','CHAR(0)','UNICHAR(-1)',
            'DATE(10000,1,1)','DATEDIF(DATE(2024,1,2),DATE(2024,1,1),"D")',
            'YEARFRAC(DATE(2024,1,1),DATE(2024,2,1),7)',
            'NETWORKDAYS.INTL(DATE(2024,1,1),DATE(2024,1,7),"1111111")',
            'CONVERT(1,"m","kg")','HEX2DEC("G1")','DEC2BIN(512)','BIN2DEC("102")',
            'DEC2BIN(31,2)','IMDIV("1+i","0")','IMREAL("nonsense")',
            'NORMDIST(1,0,-1,TRUE)','NORMINV(1.5,0,1)','BINOMDIST(11,10,0.5,FALSE)',
            'BINOMDIST(3,10,1.5,FALSE)','POISSON(2,-1,TRUE)','GAMMADIST(2,-1,1,TRUE)',
            'BETADIST(2,2,3)','TINV(1.5,4)','CHIDIST(2,-1)','FISHER(2)',
            'PMT(0.05,0,1000)','RATE(0,-100,1000)','SLN(1000,100,0)','IRR({1;2;3})',
            'PRICE(DATE(2025,1,1),DATE(2024,1,1),0.04,0.05,100,2)',
            'COUPNUM(DATE(2024,1,1),DATE(2025,1,1),3)']
    for formula in errors:add('domain-errors',formula,'Reject an invalid function domain: '+formula,error=True)
    add('lookup-arrays','HYPERLINK("https://example.invalid","Visible label")')
    add('lookup-arrays','HYPERLINK("https://example.invalid")')
    unsupported={'ISLEAPYEAR','R.DLOGIS','R.PLOGIS','R.DUNIF','R.PUNIF','PDURATION',
                 'ASEC','ACSC','ASECH','ACSCH','BAHTTEXT'}
    aliases={'PERCENTILE.INC','QUARTILE.INC','RANK.EQ','PERCENTRANK.INC','COVARIANCE.P',
             'NORM.DIST','LOGNORM.DIST','GAMMA.DIST','BINOM.DIST','POISSON.DIST'}
    # The native format uses canonical Gnumeric names; Excel spellings have
    # separate import cases in format_cases.py.
    import re
    out=[
         c for c in out if not (re.match(r'=([A-Za-z0-9_.]+)\(',c['formula']) and
           re.match(r'=([A-Za-z0-9_.]+)\(',c['formula'])[1].upper() in unsupported|aliases)]
    explicit_errors={
        '=ERROR.TYPE(ERROR("#X"))', '=NA()', '=ERROR("#N/A")',
        '=AND(FALSE,NA())','=OR(TRUE,NA())','=XOR(TRUE,NA())','=IFNA(1/0,14)',
        '=BETALN(-0.5,0.5)', '=NUMBERVALUE("$1,000",",")',
        '=SEARCH("c*c","Cancún",2)', '=SEARCHB("n*n","Cancún",4)',
        '=MIDB("Lévy",3,2)', '=FINDB("v","Lévy",5)', '=SEARCHB("n","Cancún",6)', '=REPLACEB("Lévy",2,1,"*")',
        '=REPLACEB("Lévy",3,2,"*")', '=REPLACEB("Lévy",3,3,"*")',
    }
    out=[c for c in out if c['formula']!='=T(64)']
    for c in out:
        if c['formula']=='=T(15)':
            c['formula']='=T(15)&"suffix"';c['meaning']='T returns an empty text for a numeric argument.'
        if c['formula'] in explicit_errors:c['error']=True
        if c['formula']=='=NETWORKDAYS.INTL(DATE(2024,1,1),DATE(2024,1,7),"1111111")':
            c['error']=False;c['meaning']='A calendar with every weekday marked as a weekend has zero working days.'
    return out
