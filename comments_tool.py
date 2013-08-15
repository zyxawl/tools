#!/usr/bin/python
#
# Functionality:
# 1. count lines of code and lines of comments
# 2. get the blocks of code lacking comments based on the given rule
# 3. output the result to a JSON file
# 4. support parsing single/multiple files or the whole directory
#
# Example to run:
# python comments_tool.py -d /path/to/src/ -o a.JSON --cfile --hfile --rule 25
#

import os
import re
import sys
import json
from optparse import OptionParser
from fnmatch import fnmatch

exp1_start = re.compile('/\*')
exp1_end = re.compile('\*/\s*$')

exp2_start = re.compile('//')
exp2_continue = re.compile(r'\\\n')


def run(source_file, rule=20):
    lcount, ccount = 0, 0

    try:
        f = open(source_file, 'r')
    except IOError:
        print "failed to open file %s" % source_file
        return 0, 0, None

    ml_flag_1 = False
    ml_flag_2 = False
    violate_flag = False
    no_comment_lines = 0
    illegal_blocks = []

    for line in f.readlines():
        lcount += 1
        if not ml_flag_1 and not ml_flag_2:
            if (exp1_start.search(line) and
                    not is_within_quotes(line, '/*') and
                    exp2_start.search(line) and
                    not is_within_quotes(line, '//')):

                # compare the pos of // and /*
                ret = compare_pos(line)
                if ret == 1:
                    # /* style it is
                    if not exp1_end.search(line):
                        ml_flag_1 = True
                else:
                    # go for the // style check
                    if exp2_continue.search(line):
                        ml_flag_2 = True

                ccount, no_comment_lines, violate_flag = \
                    found_comment(ccount, lcount, no_comment_lines,
                                  violate_flag, illegal_blocks)

            elif exp1_start.search(line) and not is_within_quotes(line, '/*'):
                ccount, no_comment_lines, violate_flag = \
                    found_comment(ccount, lcount, no_comment_lines,
                                  violate_flag, illegal_blocks)

                if not exp1_end.search(line):
                    ml_flag_1 = True

            elif exp2_start.search(line) and not is_within_quotes(line, '//'):
                ccount, no_comment_lines, violate_flag = \
                    found_comment(ccount, lcount, no_comment_lines,
                                  violate_flag, illegal_blocks)

                if exp2_continue.search(line):
                    ml_flag_2 = True

            else:
                no_comment_lines += 1

        elif ml_flag_1:
            ccount, no_comment_lines, violate_flag = \
                found_comment(ccount, lcount, no_comment_lines,
                              violate_flag, illegal_blocks)

            if exp1_end.search(line):
                ml_flag_1 = False

        elif ml_flag_2:
            ccount, no_comment_lines, violate_flag = \
                found_comment(ccount, lcount, no_comment_lines,
                              violate_flag, illegal_blocks)

            if not exp2_continue.search(line):
                ml_flag_2 = False

        if no_comment_lines >= rule:
            violate_flag = True

    f.close()
    return lcount, ccount, illegal_blocks


def is_within_quotes(string, sub_string):
    index_1st = string.find('\"')
    if index_1st != -1:
        pos = string.find(sub_string)
        if index_1st < pos:
            count = string.count('\"', index_1st, pos)
            if count % 2 != 0:
                return True
    return False


def compare_pos(string, pattern1='/*', pattern2='//'):
    pattern1_pos = string.find(pattern1)
    pattern2_pos = string.find(pattern2)
    if pattern1_pos < pattern2_pos:
        return 1
    else:
        return 2


def found_comment(ccount, lcount, no_comment_lines,
                  violate_flag, illegal_blocks):
    ccount += 1
    if violate_flag:
        illegal_blocks.append({'start': lcount - no_comment_lines,
                               'end': lcount - 1})
        violate_flag = False
    no_comment_lines = 0

    return ccount, no_comment_lines, violate_flag


def parse_options():
    p = OptionParser()

    p.add_option("-f", "--file", dest="filename", type="string",
                 default=None, action="append", help="File to analyze")

    p.add_option("-d", "--dir", dest="directory", type="string",
                 default=None, help="Directory to analyze")

    p.add_option("-r", "--rule", dest="rule", type="int",
                 default=20, help="The rule to specify max number of lines "
                 "of code without a comment")

    p.add_option("-j", "--json-output", dest="json", type="string",
                 default=None, help="The json output file")

    p.add_option("-t", "--text-output", dest="text", type="string",
                 default=None, help="The text output file")

    p.add_option("--cfile", dest="cfile", action="store_true",
                 default=False, help="Analyze .c files")

    p.add_option("--hfile", dest="hfile", action="store_true",
                 default=False, help="Analyze .h files")

    opts, args = p.parse_args()
    if not opts.filename and not opts.directory:
        p.print_help()
        p.error("\n\nInvalid arguments. See help above")

    if opts.filename and opts.directory:
        p.print_help()
        p.error("\n\nInvalid arguments. See help above")

    if opts.directory and not opts.cfile and not opts.hfile:
        p.print_help()
        p.error("\n\nNo file type specified. See help above")

    files = []
    if opts.filename:
        for i, opt in enumerate(opts.filename):
            if opt:
                patterns = ["*.c", "*.h"]
                if fnmatch(opt, patterns[0]):
                    files.append((".c file", opt))
                elif fnmatch(opt, patterns[1]):
                    files.append((".h file", opt))
                else:
                    p.print_help()
                    p.error("\n\nFile extension not supported. See help above")

    if opts.directory:
        patterns = []
        if opts.cfile:
            patterns.append("*.c")
        if opts.hfile:
            patterns.append("*.h")

        for path, subdirs, names in os.walk(opts.directory):
            for name in names:
                for pattern in patterns:
                    if fnmatch(name, pattern):
                        filetype = (".c file" if pattern == patterns[0] else
                                    ".h file")
                        files.append((filetype, os.path.join(path, name)))
                        break

    return opts, files


def main():
    opts, files = parse_options()

    tlc = 0
    tcc = 0
    tic = 0
    fnum = 1
    d = {}

    for ft in files:
        t = ft[0]
        f = ft[1]

        print "processing %(t)s: %(f)s..." % locals()
        lc, cc, illegal_blocks = run(f, opts.rule)
        print "lines of code: %(lc)s\nlines of comments: %(cc)s" % locals()

        if illegal_blocks:
            for i in illegal_blocks:
                print ("Blocks violate the specified rule: [%d, %d]" %
                       (i['start'], i['end']))
                tic += i['end'] - i['start'] + 1

        key = 'file ' + str(fnum)
        d.update({key: {"file name": f,
                        "lines of code": lc,
                        "lines of comments": cc,
                        "illegal blocks": illegal_blocks}})

        tlc += lc
        tcc += cc
        fnum += 1

    print ("total lines of code = %(tlc)s\n"
           "total lines of comments = %(tcc)s\n"
           "total lines of illegal blocks = %(tic)s" % locals())

    d.update({"total": {"lines of code": tlc,
                        "lines of comments": tcc,
                        "lines of illegal blocks": tic}})

    # output the result to a .JSON file if specified
    if opts.json:
        json.dump(d, open(opts.json, 'w'))

    # output the result to a .txt file if specified
    if opts.text:
        fp = open(opts.text, 'w')
        fp.write("%-50s %-20s %-20s %s\n" % ("File Name", "Lines of Code",
                 "Lines of Comments", "Illegal Blocks"))

        for i in range(fnum - 1):
            key = 'file ' + str(i + 1)
            fp.write("%-50s %-20s %-20s" % (d[key]["file name"], d[key]["lines of code"],
                     d[key]["lines of comments"]))

            ib = ""
            for l in d[key]["illegal blocks"]:
                ib += '[' + str(l['start']) + ', ' + str(l['end']) + '] '

            fp.write("%s\n" % ib)

    return 0


if __name__ == "__main__":
    sys.exit(main())
