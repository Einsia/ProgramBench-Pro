'''GUI episodes: percentage and temperature tools driven by an evaluator.'''
from gbuild import be, cp, episode
from pbuild import multi, outs

INPUTS = {'type': 'inputs'}


def fill(value, placeholder, nth=0):
    step = {'do': 'fill', 'value': value, 'placeholder': placeholder}
    if nth:
        step['nth'] = nth
    return step


def percentage():
    page = '/percentage-calculator'
    def seen(n):
        '''The result of calculator n only.'''
        return multi(result=outs(start=n, stop=n + 1, allow_empty=True))

    follow = 'The result follows the two numbers.'
    return episode('gui-percentage', 'math', [
        cp('of', 'On the percentage calculator, use the first calculator to find 10 percent of 200.', 'The first calculator shows the result 20.',
           [fill('10', 'X'), fill('200', 'Y')], [be('results', follow, seen(0))], page=page),
        cp('part', 'On the percentage calculator, use the second calculator to find what percent 5 is of 20.', 'The second calculator shows the result 25.',
           [fill('5', 'X', 1), fill('20', 'Y', 1)], [be('results', follow, seen(1))], page=page),
        cp('change', 'On the percentage calculator, use the third calculator to find the percentage change from 50 to 75.', 'The third calculator shows the result 50.',
           [fill('50', 'From'), fill('75', 'To')], [be('results', follow, seen(2))], page=page),
        cp('decrease', 'On the percentage calculator, use the third calculator to find the percentage change from 80 to 60.', 'The third calculator shows the result -25.',
           [fill('80', 'From'), fill('60', 'To')], [be('results', follow, seen(2), ['change/results'])], page=page, requires=['change/results']),
        cp('zero', 'On the percentage calculator, use the second calculator to find what percent 5 is of 0.', 'The second calculator shows no result.',
           [fill('5', 'X', 1), fill('0', 'Y', 1)], [be('results', 'No result is shown for a whole of zero.', seen(1), ['part/results'])], page=page, requires=['part/results']),
    ])


def temperature():
    page = '/temperature-converter'
    follow = 'The other scales follow the typed value.'
    return episode('gui-temperature', 'measurement', [
        cp('celsius', 'On the temperature converter, type 100 in the Celsius field and read the Kelvin field.', 'The Kelvin field shows 373.15.',
           [fill('100', 'Please Input', 1)], [be('scales', follow, INPUTS)], page=page),
        cp('fahrenheit', 'On the temperature converter, type 32 in the Fahrenheit field and read the Celsius and Kelvin fields.', 'The Celsius field shows 0 and the Kelvin field shows 273.15.',
           [fill('32', 'Please Input', 2)], [be('scales', follow, INPUTS)], page=page),
        cp('kelvin', 'On the temperature converter, type 0 in the Kelvin field and read the Celsius field.', 'The Celsius field shows -273.15.',
           [fill('0', 'Please Input', 0)], [be('scales', follow, INPUTS)], page=page),
        cp('minus-forty', 'On the temperature converter, type -40 in the Fahrenheit field and read the Celsius field.', 'The Celsius field shows -40.',
           [fill('-40', 'Please Input', 2)], [be('scales', follow, INPUTS, ['celsius/scales'])], page=page, requires=['celsius/scales']),
    ])


def build():
    return [percentage(), temperature()]
