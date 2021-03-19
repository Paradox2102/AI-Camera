import csv

PATH = 'Data'

def f():
    for i in range(1,4):
        with open(f'{PATH}/imageData{i}.csv') as csvfile:
            for row in csv.reader(csvfile):
                yield [row[0][2:], 640, 480, 'ball', *row[1:]]

with open('final.csv', 'w') as csvfile:
    for row in f():
        csv.writer(csvfile).writerow(row)
