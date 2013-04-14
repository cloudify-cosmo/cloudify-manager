# vim: set filetype=ruby et sw=2 ts=2:

require 'gem_hadar'

GemHadar do
  name        'tins'
  author      'Florian Frank'
  email       'flori@ping.de'
  homepage    "http://flori.github.com/#{name}"
  summary     'Useful stuff.'
  description 'All the stuff that isn\'t good/big enough for a real library.'
  test_dir    'tests'
  test_files.concat Dir["#{test_dir}/*_test.rb"]
  ignore      '.*.sw[pon]', 'pkg', 'Gemfile.lock', '.rvmrc', 'coverage', '.rbx',
              '.AppleDouble'


  readme      'README.rdoc'

  development_dependency 'test-unit', '~>2.5'
  development_dependency 'utils'

  install_library do
    libdir = CONFIG["sitelibdir"]
    cd 'lib' do
      for file in Dir['**/*.rb']
        dst = File.join(libdir, file)
        mkdir_p File.dirname(dst)
        install file, dst
      end
    end
    install 'bin/enum', File.join(CONFIG['bindir'], 'enum')
  end
end
