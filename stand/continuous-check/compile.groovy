def loader=new GroovyClassLoader(this.class.classLoader)
args.each { loader.parseClass(new File(it));println('Compiled '+it) }
