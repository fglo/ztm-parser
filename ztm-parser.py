import sys
import os
import json
import re
import ntpath
from enum import Enum

def logInfo(message):
    print("INFO:", message)

def logERROR(message):
    print("ERROR:", message)

class FileSection(Enum):
    NONE = 0
    LL = 1
    TR = 2
    WK = 3
    RP = 4
    TD = 5
    OP = 6
    OD = 7

class RaFileParser:
    def __init__(self):
        self.lines = []
        self.fileSection = FileSection.NONE


    def parseFile(self, filepath):
        self.filepath = filepath
        self.filenameBase = ntpath.basename(filepath).rsplit('.', 1)[0]

        logInfo("TRYING TO OPEN " + self.filepath)

        if not os.path.isfile(self.filepath):
            logERROR(f"FILE PATH {self.filepath} DOES NOT EXIST")
            return False

        logInfo("PARSING STARTED")

        with open(self.filepath) as fp:
            for file_line in fp:  
                self.parse(file_line)

        logInfo("PARSING IS DONE")

        return True

    def parse(self, file_line):
        if self.fileSection == FileSection.NONE:
            if "*LL" in file_line:
                self.fileSection = FileSection.LL
        elif self.fileSection == FileSection.LL:
            if "#LL" in file_line:
                self.fileSection = FileSection.NONE
            elif (not self.lines or self.lines[-1].ended) and "LINIA KOLEI MIEJSKIEJ" in file_line:
                self.lines.append(Line(file_line))
            elif self.lines and not self.lines[-1].ended:
                self.lines[-1].parse(file_line)
        

    def serializeToCSV(self):
        logInfo("SERIALIZING TO CSV")
        csv = []
        csv.append("line_number;description;route_id;original_stop;last_stop;direction;stop_id;stop_name;valid_from;valid_until;timetable_type;timetable_desc;departure_time;departure_id")
        for line in self.lines:
            csv.extend(line.serializeToCSV())

        filename = f'./{self.filenameBase}.CSV'
        logInfo(f"SAVING OUTPUT IN {filename}")
    
        with open(filename, 'w') as filehandle:
            filehandle.writelines("%s\n" % csv_line for csv_line in csv)

    def serializeToJSON(self):
        logInfo("SERIALIZING TO JSON")
        json_lines = json.dumps(self.lines, cls=ComplexEncoder, indent=4, sort_keys=True)

        filename = f'./{self.filenameBase}.JSON'
        logInfo(f"SAVING OUTPUT IN {filename}")
        
        with open(filename, 'w') as filehandle:
            filehandle.write(json_lines)

class Line:
    def __init__(self, file_line):
        fields = [field.strip() for field in file_line.split('-')]
        
        self.line_number =  [field.strip() for field in fields[0].split(':')][1]
        self.description = fields[1]

        print("  => Added line", self.line_number)

        self.routes = []

        self.ended = False
        self.fileSection = FileSection.LL

    def parse(self, file_line):
        if self.fileSection == FileSection.LL:
            if "*TR" in file_line:
                self.fileSection = FileSection.TR
            elif "*WK" in file_line:
                self.fileSection = FileSection.WK
        elif self.fileSection == FileSection.TR:
            if "#TR" in file_line:
                self.fileSection = FileSection.LL
            elif not self.routes or self.routes[-1].ended:
                self.routes.append(Route(file_line))
            elif self.routes and not self.routes[-1].ended:
                self.routes[-1].parse(file_line)
        elif self.fileSection == FileSection.WK:
            if "#WK" in file_line:
                self.fileSection = FileSection.LL
                self.ended = True

    def serializeToCSV(self):
        csv_lines = []
        csv_line = self.line_number + ";" + self.description + ";"
        for route in self.routes:
            csv_lines.extend(route.serializeToCSV(csv_line))

        return csv_lines

    def reprJSON(self):
        return dict(line_number=self.line_number, description=self.description, routes=self.routes)


class Route:
    def __init__(self, file_line):
        fields = [field.strip() for field in file_line.split(',')]

        self.route_id = fields[0]
        self.original_stop = fields[1]
        self.last_stop = [field.strip() for field in fields[2].split('==>')][1]
        fields = [field.strip() for field in fields[3].strip().split()]
        self.direction = fields[2]

        self.stops = []

        self.ended = False
        self.fileSection = FileSection.TR

    def parse(self, file_line):
        if self.fileSection == FileSection.TR:
            if "*RP" in file_line:
                self.fileSection = FileSection.RP
        elif self.fileSection == FileSection.RP:
            if "#RP" in file_line:
                self.fileSection = FileSection.TR
                self.ended = True
            elif not self.stops or self.stops[-1].ended:
                self.stops.append(Stop(file_line))
            elif self.stops and not self.stops[-1].ended:
                self.stops[-1].parse(file_line)

    def serializeToCSV(self, csv_line):
        csv_lines = []
        csv_line += self.route_id + ";" + self.original_stop + ";" + self.last_stop + ";" + self.direction + ";"
        for stop in self.stops:
            csv_lines.extend(stop.serializeToCSV(csv_line))

        return csv_lines

    def reprJSON(self):
        return dict(route_id=self.route_id, original_stop=self.original_stop, last_stop=self.last_stop, direction=self.direction, stops=self.stops)
    

class Stop:
    def __init__(self, file_line):
        fields = [field.strip() for field in file_line.split(',')]
        fields = [field.strip() for field in fields[0].split('  ')]

        self.stop_id = fields[0]
        self.stop_name = fields[1]
        self.valid_from = ""
        self.valid_until = ""

        self.timetables = []
        
        self.ended = False
        self.fileSection = FileSection.RP

    def parse(self, file_line):
        if self.fileSection == FileSection.RP:
            if "*TD" in file_line:
                self.fileSection = FileSection.TD
            elif "*OP" in file_line:
                self.fileSection = FileSection.OP
        elif self.fileSection == FileSection.TD:
            if "#TD" in file_line:
                self.fileSection = FileSection.RP
            elif not self.timetables or self.timetables[-1].ended:
                self.timetables.append(Timetable(file_line))
            elif self.timetables and not self.timetables[-1].ended:
                self.timetables[-1].parse(file_line)
        elif self.fileSection == FileSection.OP:
            if "#OP" in file_line:
                self.fileSection = FileSection.RP
                self.ended = True
            elif re.compile('.*rozk.+ad wa.+ny od.*', re.IGNORECASE).match(file_line):
                fields = [field.strip() for field in file_line.split('od')]
                self.valid_from = fields[1][1:].strip() if fields[1][0] == ':' else fields[1]
            elif re.compile('.*rozk.+ad jazdy obowi.+zuje w dniach.*', re.IGNORECASE).match(file_line):
                fields = [field.strip() for field in file_line.split(':')]
                fields = [field.strip() for field in fields[1].split('-')]
                self.valid_from = fields[0]
                self.valid_until = fields[1][:-1].strip() if fields[1][-1] == '.' else fields[1]

    def serializeToCSV(self, csv_line):
        csv_lines = []
        csv_line += self.stop_id + ";" + self.stop_name + ";" + self.valid_from + ";" + self.valid_until + ";"
        for timetable in self.timetables:
            csv_lines.extend(timetable.serializeToCSV(csv_line))

        return csv_lines

    def reprJSON(self):
        return dict(stop_id=self.stop_id, stop_name=self.stop_name, timetables=self.timetables, valid_from=self.valid_from, valid_until=self.valid_until)


class Timetable:
    def __init__(self, file_line):
        fields = [field.strip() for field in file_line.strip().split('  ')]

        self.timetable_type = fields[0]
        self.timetable_desc = fields[1]

        self.departures = []
        
        self.ended = False
        self.fileSection = FileSection.TD

    def parse(self, file_line):
        if self.fileSection == FileSection.TD:
            if "*OD" in file_line:
                self.fileSection = FileSection.OD
        elif self.fileSection == FileSection.OD:
            if "#OD" in file_line:
                self.fileSection = FileSection.TD
                self.ended = True
            else:
                self.departures.append(Departure(file_line))

    def serializeToCSV(self, csv_line):
        csv_lines = []
        csv_line += self.timetable_type + ";" + self.timetable_desc + ";"
        for departure in self.departures:
            csv_lines.append(departure.serializeToCSV(csv_line))

        return csv_lines

    def reprJSON(self):
        return dict(timetable_type=self.timetable_type, timetable_desc=self.timetable_desc, departures=self.departures)

class Departure:
    def __init__(self, file_line):
        fields = [field.strip() for field in file_line.split()]

        self.departure_time = fields[0].replace(".", ":")
        self.departure_id = fields[1]

    def serializeToCSV(self, csv_line):
        csv_line += self.departure_time + ";" + self.departure_id 
        return csv_line

    def reprJSON(self):
        return dict(departure_time=self.departure_time, departure_id=self.departure_id)

class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj,'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)

def printHelp():
    print('ZTM PARSER:')
    print('  HELP: python parser.py help')
    print('  PARSER: python parser.py <FILEPATH>')
    print('  CHANGE OUTPUT: python parser.py <FILEPATH> -out <OUTPUT VARIANTS>')
    print('    OUTPUT VARIANTS:')
    print('      -out json')
    print('      -out csv')
    print('      -out json,csv')
    print('      -out csv,json')

def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        print("Enter the input file:")
        filepath = input()

    if filepath == 'help':
        printHelp()
        return
    else:
        printJson = True
        printCsv = True

        if len(sys.argv) > 3 and '-out' in sys.argv[2]:
            printJson = 'json' in sys.argv[3]
            printCsv = 'csv' in sys.argv[3]

        logInfo("STARTING")
        
        parser = RaFileParser()
        if parser.parseFile(filepath):
            if printJson:
                parser.serializeToJSON()
            if printCsv:
                parser.serializeToCSV()

        logInfo("FINISHED")

if __name__ == '__main__':
    main()
