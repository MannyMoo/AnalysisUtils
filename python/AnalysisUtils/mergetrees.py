from AnalysisUtils.treeutils import merge_trees_to_file

if __name__ == '__main__' :
    import sys
    args = sys.argv[1:]
    outputfname = args.pop(0)
    treeNames = zip(args[::2], args[1::2])
    merge_trees_to_file(outputfname, *treeNames)
    
